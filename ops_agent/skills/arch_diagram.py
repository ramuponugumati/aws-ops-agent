"""Architecture Diagram — scan resources by tag/account and generate a visual architecture map."""
import time
import json
import os
from ops_agent.core import BaseSkill, SkillResult, Finding, Severity
from ops_agent.aws_client import get_client, get_account_id, parallel_regions


class ArchDiagramSkill(BaseSkill):
    name = "arch-diagram"
    description = "Discover resources and generate solution architecture diagrams by tag or account"
    version = "0.1.0"

    def scan(self, regions, profile=None, account_id=None, **kwargs) -> SkillResult:
        start = time.time()
        findings = []
        errors = []
        acct = account_id or get_account_id(profile)
        tag_filter = kwargs.get("tag_filter", None)  # e.g. {"Environment": "prod"}
        scan_regions = regions[:3]
        config_resources, config_relationships, cloudtrail_calls = {}, [], []
        try:
            config_resources, config_relationships = self._discover_via_config(scan_regions[0], profile)
        except Exception:
            pass
        try:
            cloudtrail_calls = self._discover_via_cloudtrail(scan_regions[0], profile)
        except Exception:
            pass

        # Discover resources across services
        resources = {"ec2": [], "rds": [], "lambda": [], "ecs": [], "elb": [], "s3": [], "vpc": [], "api_gw": [], "dynamodb": [], "sqs": [], "sns": [], "cloudfront": []}

        try:
            results = parallel_regions(lambda r: self._discover_ec2(r, profile, tag_filter), scan_regions)
            resources["ec2"].extend(results)
        except Exception as e:
            errors.append(f"ec2: {e}")

        try:
            results = parallel_regions(lambda r: self._discover_rds(r, profile), scan_regions)
            resources["rds"].extend(results)
        except Exception as e:
            errors.append(f"rds: {e}")

        try:
            results = parallel_regions(lambda r: self._discover_lambda(r, profile), scan_regions)
            resources["lambda"].extend(results)
        except Exception as e:
            errors.append(f"lambda: {e}")

        try:
            results = parallel_regions(lambda r: self._discover_elb(r, profile), scan_regions)
            resources["elb"].extend(results)
        except Exception as e:
            errors.append(f"elb: {e}")

        try:
            results = parallel_regions(lambda r: self._discover_ecs(r, profile), scan_regions)
            resources["ecs"].extend(results)
        except Exception as e:
            errors.append(f"ecs: {e}")

        try:
            results = parallel_regions(lambda r: self._discover_vpc(r, profile), scan_regions)
            resources["vpc"].extend(results)
        except Exception as e:
            errors.append(f"vpc: {e}")

        try:
            resources["s3"] = self._discover_s3(profile)
        except Exception as e:
            errors.append(f"s3: {e}")

        # API Gateway
        try:
            results = parallel_regions(lambda r: self._discover_apigw(r, profile), scan_regions)
            resources["api_gw"].extend(results)
        except Exception as e:
            errors.append(f"api_gw: {e}")

        # DynamoDB
        try:
            results = parallel_regions(lambda r: self._discover_dynamodb(r, profile), scan_regions)
            resources["dynamodb"].extend(results)
        except Exception as e:
            errors.append(f"dynamodb: {e}")

        # SQS
        try:
            results = parallel_regions(lambda r: self._discover_sqs(r, profile), scan_regions)
            resources["sqs"].extend(results)
        except Exception as e:
            errors.append(f"sqs: {e}")

        # SNS
        try:
            results = parallel_regions(lambda r: self._discover_sns(r, profile), scan_regions)
            resources["sns"].extend(results)
        except Exception as e:
            errors.append(f"sns: {e}")

        # CloudFront (global)
        try:
            resources["cloudfront"] = self._discover_cloudfront(profile)
        except Exception as e:
            errors.append(f"cloudfront: {e}")

        # Generate architecture findings — one per resource category
        total = sum(len(v) for v in resources.values())
        if total > 0:
            diagram_text = self._generate_diagram_text(resources, acct)
            mermaid = self._generate_mermaid_diagram(resources, acct, profile, config_resources, config_relationships, cloudtrail_calls)
            # Summary finding with full diagram
            findings.append(Finding(
                skill=self.name,
                title=f"Architecture Map: {total} resources across {len([v for v in resources.values() if v])} services",
                severity=Severity.INFO, region="all",
                resource_id=acct,
                description=diagram_text,
                recommended_action="View diagram below",
                metadata={
                    "resources": {k: len(v) for k, v in resources.items()},
                    "diagram": diagram_text, "mermaid": mermaid,
                    "config_resources": len(config_resources),
                    "relationships": len(config_relationships),
                    "cloudtrail_calls": len(cloudtrail_calls),
                },
            ))
            # Individual findings per service for the table
            svc_names = {"ec2": "EC2 Instances", "rds": "RDS Databases", "lambda": "Lambda Functions",
                        "ecs": "ECS Clusters", "elb": "Load Balancers", "vpc": "VPCs", "s3": "S3 Buckets",
                        "api_gw": "API Gateways", "dynamodb": "DynamoDB Tables", "sqs": "SQS Queues",
                        "sns": "SNS Topics", "cloudfront": "CloudFront Distributions"}
            for svc, items in resources.items():
                if not items:
                    continue
                desc_lines = []
                for item in items[:15]:
                    if svc == "ec2":
                        desc_lines.append(f"{item.get('id','')} ({item.get('name','')}) | {item.get('type','')} | {item.get('az','')}")
                    elif svc == "rds":
                        az = "Multi-AZ" if item.get('multi_az') else "Single-AZ"
                        desc_lines.append(f"{item.get('id','')} | {item.get('engine','')} | {item.get('class','')} | {az}")
                    elif svc == "lambda":
                        desc_lines.append(f"{item.get('name','')} | {item.get('runtime','')} | {item.get('memory',0)}MB")
                    elif svc == "elb":
                        desc_lines.append(f"{item.get('name','')} | {item.get('type','')} | {item.get('scheme','')}")
                    elif svc == "ecs":
                        desc_lines.append(f"{item.get('cluster','')} | {item.get('service_count',0)} services")
                    elif svc == "vpc":
                        desc_lines.append(f"{item.get('id','')} ({item.get('name','')}) | {item.get('cidr','')} | {item.get('subnet_count',0)} subnets")
                    elif svc == "s3":
                        desc_lines.append(item.get('name',''))
                if len(items) > 15:
                    desc_lines.append(f"... +{len(items)-15} more")
                findings.append(Finding(
                    skill=self.name,
                    title=f"{svc_names.get(svc, svc)}: {len(items)} found",
                    severity=Severity.INFO, region="all",
                    resource_id=f"{len(items)} resources",
                    description="\n".join(desc_lines),
                    recommended_action="Review resource details",
                ))

        for f in findings:
            f.account_id = acct

        return SkillResult(
            skill_name=self.name, findings=findings,
            duration_seconds=time.time() - start,
            accounts_scanned=1, regions_scanned=len(regions), errors=errors,
        )

    def _discover_ec2(self, region, profile, tag_filter=None):
        results = []
        try:
            ec2 = get_client("ec2", region, profile)
            filters = [{"Name": "instance-state-name", "Values": ["running"]}]
            if tag_filter:
                for k, v in tag_filter.items():
                    filters.append({"Name": f"tag:{k}", "Values": [v]})
            paginator = ec2.get_paginator("describe_instances")
            for page in paginator.paginate(Filters=filters):
                for res in page["Reservations"]:
                    for inst in res["Instances"]:
                        name = next((t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"), "")
                        results.append({"id": inst["InstanceId"], "name": name, "type": inst["InstanceType"],
                                       "region": region, "vpc": inst.get("VpcId", ""), "subnet": inst.get("SubnetId", ""),
                                       "az": inst["Placement"]["AvailabilityZone"]})
        except Exception:
            pass
        return results

    def _discover_rds(self, region, profile):
        results = []
        try:
            rds = get_client("rds", region, profile)
            for db in rds.describe_db_instances().get("DBInstances", []):
                results.append({"id": db["DBInstanceIdentifier"], "engine": db["Engine"],
                               "class": db["DBInstanceClass"], "region": region,
                               "multi_az": db.get("MultiAZ", False), "vpc": db.get("DBSubnetGroup", {}).get("VpcId", "")})
        except Exception:
            pass
        return results

    def _discover_lambda(self, region, profile):
        results = []
        try:
            lam = get_client("lambda", region, profile)
            for fn in lam.list_functions().get("Functions", []):
                results.append({"name": fn["FunctionName"], "runtime": fn.get("Runtime", ""),
                               "region": region, "memory": fn.get("MemorySize", 0)})
        except Exception:
            pass
        return results

    def _discover_elb(self, region, profile):
        results = []
        try:
            elb = get_client("elbv2", region, profile)
            for lb in elb.describe_load_balancers().get("LoadBalancers", []):
                results.append({"name": lb["LoadBalancerName"], "type": lb["Type"],
                               "region": region, "vpc": lb.get("VpcId", ""),
                               "dns": lb.get("DNSName", ""), "scheme": lb.get("Scheme", "")})
        except Exception:
            pass
        return results

    def _discover_ecs(self, region, profile):
        results = []
        try:
            ecs = get_client("ecs", region, profile)
            clusters = ecs.list_clusters().get("clusterArns", [])
            for arn in clusters:
                name = arn.split("/")[-1]
                services = ecs.list_services(cluster=arn).get("serviceArns", [])
                results.append({"cluster": name, "region": region, "service_count": len(services)})
        except Exception:
            pass
        return results

    def _discover_vpc(self, region, profile):
        results = []
        try:
            ec2 = get_client("ec2", region, profile)
            for vpc in ec2.describe_vpcs().get("Vpcs", []):
                name = next((t["Value"] for t in vpc.get("Tags", []) if t["Key"] == "Name"), "")
                subnets = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc["VpcId"]]}]).get("Subnets", [])
                results.append({"id": vpc["VpcId"], "name": name, "cidr": vpc["CidrBlock"],
                               "region": region, "subnet_count": len(subnets)})
        except Exception:
            pass
        return results

    def _discover_s3(self, profile):
        results = []
        try:
            s3 = get_client("s3", "us-east-1", profile)
            for bucket in s3.list_buckets().get("Buckets", []):
                results.append({"name": bucket["Name"]})
        except Exception:
            pass
        return results

    def _discover_via_config(self, region, profile):
        """Use AWS Config to discover ALL resources and their relationships."""
        resources_by_type = {}
        relationships = []
        try:
            config = get_client("config", region, profile)
            # Get all discovered resource types
            resource_types = [
                "AWS::EC2::Instance", "AWS::EC2::VPC", "AWS::EC2::Subnet", "AWS::EC2::SecurityGroup",
                "AWS::EC2::NatGateway", "AWS::EC2::InternetGateway",
                "AWS::ElasticLoadBalancingV2::LoadBalancer", "AWS::ElasticLoadBalancingV2::TargetGroup",
                "AWS::RDS::DBInstance", "AWS::RDS::DBCluster",
                "AWS::Lambda::Function", "AWS::ECS::Cluster", "AWS::ECS::Service",
                "AWS::S3::Bucket", "AWS::DynamoDB::Table",
                "AWS::SQS::Queue", "AWS::SNS::Topic",
                "AWS::ApiGateway::RestApi", "AWS::ApiGatewayV2::Api",
                "AWS::CloudFront::Distribution",
                "AWS::ElastiCache::CacheCluster", "AWS::Kinesis::Stream",
                "AWS::StepFunctions::StateMachine", "AWS::Events::Rule",
            ]
            for rtype in resource_types:
                try:
                    resp = config.list_discovered_resources(resourceType=rtype, limit=50)
                    items = resp.get("resourceIdentifiers", [])
                    if items:
                        short_type = rtype.split("::")[-1]
                        resources_by_type[short_type] = [
                            {"id": r.get("resourceId", ""), "name": r.get("resourceName", ""), "type": rtype, "region": region}
                            for r in items
                        ]
                except Exception:
                    pass

            # Get relationships from Config resource details
            for rtype, items in resources_by_type.items():
                for item in items[:10]:
                    try:
                        detail = config.get_resource_config_history(
                            resourceType=item["type"], resourceId=item["id"], limit=1
                        )
                        for ci in detail.get("configurationItems", []):
                            for rel in ci.get("relationships", []):
                                relationships.append({
                                    "source": f"{rtype}:{item['id']}",
                                    "target": f"{rel.get('resourceType','').split('::')[-1]}:{rel.get('resourceId','')}",
                                    "relation": rel.get("relationshipName", ""),
                                })
                    except Exception:
                        pass
        except Exception:
            pass
        return resources_by_type, relationships

    def _discover_via_cloudtrail(self, region, profile):
        """Use CloudTrail to find service-to-service invocations for relationship mapping."""
        from datetime import datetime, timedelta, timezone
        service_calls = []
        try:
            ct = get_client("cloudtrail", region, profile)
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=1)
            # Look for cross-service invocations
            resp = ct.lookup_events(
                StartTime=start, EndTime=end, MaxResults=50,
                LookupAttributes=[{"AttributeKey": "ReadOnly", "AttributeValue": "false"}],
            )
            for event in resp.get("Events", []):
                source = event.get("EventSource", "").replace(".amazonaws.com", "")
                target_resources = event.get("Resources", [])
                for r in target_resources:
                    service_calls.append({
                        "source_service": source,
                        "event": event.get("EventName", ""),
                        "target_type": r.get("ResourceType", ""),
                        "target_id": r.get("ResourceName", ""),
                    })
        except Exception:
            pass
        return service_calls

    def _generate_diagram_text(self, resources, account_id):
        """Generate a text-based architecture diagram."""
        lines = [f"=== Architecture Map for Account {account_id} ===\n"]

        if resources["vpc"]:
            lines.append("NETWORK LAYER:")
            for vpc in resources["vpc"]:
                lines.append(f"  VPC: {vpc['id']} ({vpc.get('name','')}) | {vpc['cidr']} | {vpc['subnet_count']} subnets | {vpc['region']}")

        if resources["elb"]:
            lines.append("\nLOAD BALANCERS:")
            for lb in resources["elb"]:
                lines.append(f"  {lb['type'].upper()}: {lb['name']} | {lb['scheme']} | {lb['region']}")

        if resources["ec2"]:
            lines.append(f"\nCOMPUTE ({len(resources['ec2'])} instances):")
            for inst in resources["ec2"][:20]:
                lines.append(f"  EC2: {inst['id']} ({inst['name']}) | {inst['type']} | {inst['az']}")

        if resources["ecs"]:
            lines.append("\nCONTAINERS:")
            for c in resources["ecs"]:
                lines.append(f"  ECS Cluster: {c['cluster']} | {c['service_count']} services | {c['region']}")

        if resources["lambda"]:
            lines.append(f"\nSERVERLESS ({len(resources['lambda'])} functions):")
            for fn in resources["lambda"][:20]:
                lines.append(f"  Lambda: {fn['name']} | {fn['runtime']} | {fn['region']}")

        if resources["rds"]:
            lines.append("\nDATABASES:")
            for db in resources["rds"]:
                az = "Multi-AZ" if db['multi_az'] else "Single-AZ"
                lines.append(f"  RDS: {db['id']} | {db['engine']} | {db['class']} | {az} | {db['region']}")

        if resources["s3"]:
            lines.append(f"\nSTORAGE ({len(resources['s3'])} buckets):")
            for b in resources["s3"][:10]:
                lines.append(f"  S3: {b['name']}")

        return "\n".join(lines)

    def _generate_mermaid_diagram(self, resources, account_id, profile, config_resources=None, config_relationships=None, cloudtrail_calls=None):
        """Use Bedrock Haiku 4.5 to generate a Mermaid architecture diagram with relationship data."""
        try:
            bedrock = get_client("bedrock-runtime", "us-east-1", profile)
            summary = f"AWS Account: {account_id}\n\nRESOURCES DISCOVERED:\n"
            for svc, items in resources.items():
                if not items:
                    continue
                summary += f"\n{svc.upper()} ({len(items)}):\n"
                for item in items[:10]:
                    summary += f"  {json.dumps(item)}\n"

            # Add Config-discovered resources not in direct API results
            if config_resources:
                summary += "\n\nADDITIONAL RESOURCES FROM AWS CONFIG:\n"
                for rtype, items in config_resources.items():
                    summary += f"  {rtype}: {len(items)} resources\n"
                    for item in items[:5]:
                        summary += f"    - {item.get('name', item.get('id', ''))}\n"

            # Add relationships from Config
            if config_relationships:
                summary += f"\n\nRESOURCE RELATIONSHIPS ({len(config_relationships)} found):\n"
                for rel in config_relationships[:30]:
                    summary += f"  {rel['source']} --{rel['relation']}--> {rel['target']}\n"

            # Add CloudTrail service calls
            if cloudtrail_calls:
                summary += f"\n\nSERVICE-TO-SERVICE CALLS FROM CLOUDTRAIL ({len(cloudtrail_calls)} events):\n"
                seen = set()
                for call in cloudtrail_calls[:20]:
                    key = f"{call['source_service']}->{call['target_type']}"
                    if key not in seen:
                        seen.add(key)
                        summary += f"  {call['source_service']} calls {call['event']} on {call['target_type']}:{call['target_id']}\n"

            prompt = (
                "Generate a Mermaid.js architecture diagram for this AWS account. "
                "Use graph TD (top-down). Rules:\n"
                "- Group resources inside VPC subgraphs when VPC info is available\n"
                "- Show actual connections based on the RELATIONSHIPS and CLOUDTRAIL data\n"
                "- Use arrows to show data flow: Internet->CloudFront->ALB->EC2->RDS\n"
                "- Show Lambda triggers: API GW->Lambda->DynamoDB, SQS->Lambda, SNS->Lambda\n"
                "- Use meaningful labels on arrows (e.g., 'HTTP', 'invoke', 'query')\n"
                "- Use icons in node labels: e.g., 'EC2[🖥 EC2 instance-name]'\n"
                "- Keep it clean — max 30 nodes. Group similar resources.\n"
                "- ONLY output valid Mermaid code. Start with 'graph TD'. No markdown fences.\n\n"
                f"{summary}"
            )

            response = bedrock.invoke_model(
                modelId=os.environ.get("OPS_AGENT_BEDROCK_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "messages": [{"role": "user", "content": prompt}],
                    "system": "You are an AWS architecture diagram generator. Output ONLY valid Mermaid.js code. No markdown fences, no explanation. Use the relationship data to draw accurate connections between resources.",
                    "max_tokens": 3000,
                }),
            )
            body = json.loads(response["body"].read())
            mermaid = body["content"][0]["text"].strip()
            if mermaid.startswith("```"):
                mermaid = mermaid.split("\n", 1)[1] if "\n" in mermaid else mermaid[3:]
            if mermaid.endswith("```"):
                mermaid = mermaid[:-3].strip()
            return mermaid
        except Exception as e:
            return f"graph TD\n  A[Error generating diagram: {str(e)[:80]}]"
