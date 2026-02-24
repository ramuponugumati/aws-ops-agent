"""Security Hub Analyzer — pull Security Hub findings and map to automated remediations."""
import time
from ops_agent.core import BaseSkill, SkillResult, Finding, Severity
from ops_agent.aws_client import get_client, get_account_id, parallel_regions

# Map Security Hub severity labels to our severity
SEVERITY_MAP = {"CRITICAL": Severity.CRITICAL, "HIGH": Severity.HIGH, "MEDIUM": Severity.MEDIUM, "LOW": Severity.LOW, "INFORMATIONAL": Severity.INFO}

# Common CIS/FSBP controls with automated remediation guidance
CONTROL_REMEDIATION = {
    "CIS.1.4": "Enable MFA on root account",
    "CIS.1.5": "Enable MFA on IAM users with console access",
    "CIS.1.10": "Enable MFA for IAM users with console password",
    "CIS.2.1": "Enable CloudTrail in all regions",
    "CIS.2.6": "Enable S3 bucket access logging on CloudTrail bucket",
    "CIS.2.7": "Enable CloudTrail log file validation",
    "CIS.2.9": "Enable VPC Flow Logs in all VPCs",
    "CIS.3.1": "Create CloudWatch log metric filter for unauthorized API calls",
    "CIS.4.1": "Restrict SSH access in security groups",
    "CIS.4.2": "Restrict RDP access in security groups",
    "S3.1": "Enable S3 Block Public Access at account level",
    "S3.2": "S3 buckets should prohibit public read access",
    "S3.5": "S3 buckets should require SSL",
    "EC2.2": "VPC default security group should restrict all traffic",
    "EC2.19": "Security groups should not allow unrestricted access to high risk ports",
    "IAM.1": "IAM policies should not allow full * administrative privileges",
    "IAM.4": "IAM root user access key should not exist",
    "RDS.1": "RDS snapshots should be private",
    "RDS.2": "RDS instances should prohibit public access",
    "RDS.3": "RDS instances should have encryption at rest enabled",
}


class SecurityHubSkill(BaseSkill):
    name = "security-hub"
    description = "Analyze Security Hub findings across CIS, FSBP, and PCI-DSS standards with remediation guidance"
    version = "0.1.0"

    def scan(self, regions, profile=None, account_id=None, **kwargs) -> SkillResult:
        start = time.time()
        findings = []
        errors = []
        acct = account_id or get_account_id(profile)

        try:
            results = parallel_regions(lambda r: self._check_security_hub(r, profile), regions)
            findings.extend(results)
        except Exception as e:
            errors.append(f"security-hub: {e}")

        for f in findings:
            f.account_id = acct

        return SkillResult(
            skill_name=self.name, findings=findings,
            duration_seconds=time.time() - start,
            accounts_scanned=1, regions_scanned=len(regions), errors=errors,
        )

    def _check_security_hub(self, region, profile):
        findings = []
        try:
            sh = get_client("securityhub", region, profile)

            # Get active findings grouped by control
            resp = sh.get_findings(
                Filters={
                    "WorkflowStatus": [{"Value": "NEW", "Comparison": "EQUALS"}, {"Value": "NOTIFIED", "Comparison": "EQUALS"}],
                    "RecordState": [{"Value": "ACTIVE", "Comparison": "EQUALS"}],
                    "ComplianceStatus": [{"Value": "FAILED", "Comparison": "EQUALS"}],
                },
                MaxResults=100,
                SortCriteria=[{"Field": "SeverityLabel", "SortOrder": "desc"}],
            )

            # Deduplicate by control ID — group findings per control
            controls_seen = {}
            for f in resp.get("Findings", []):
                control_id = f.get("Compliance", {}).get("SecurityControlId", "") or f.get("GeneratorId", "").split("/")[-1]
                sev_label = f.get("Severity", {}).get("Label", "INFORMATIONAL")
                title = f.get("Title", "")
                resource_type = ""
                resource_id = ""
                resources = f.get("Resources", [])
                if resources:
                    resource_type = resources[0].get("Type", "")
                    resource_id = resources[0].get("Id", "").split("/")[-1]  # Shorten ARNs

                if control_id not in controls_seen:
                    controls_seen[control_id] = {
                        "title": title, "severity": sev_label,
                        "resources": [], "count": 0,
                    }
                controls_seen[control_id]["count"] += 1
                if len(controls_seen[control_id]["resources"]) < 5:
                    controls_seen[control_id]["resources"].append(resource_id)

            for control_id, info in controls_seen.items():
                sev = SEVERITY_MAP.get(info["severity"], Severity.INFO)
                remediation = CONTROL_REMEDIATION.get(control_id, "Review in Security Hub console")
                resource_list = ", ".join(info["resources"][:3])
                if info["count"] > 3:
                    resource_list += f" (+{info['count']-3} more)"

                findings.append(Finding(
                    skill=self.name,
                    title=f"{control_id}: {info['title'][:60]}",
                    severity=sev, region=region,
                    resource_id=resource_list,
                    description=f"{info['count']} resource(s) failing this control",
                    recommended_action=remediation,
                    metadata={"control_id": control_id, "failing_count": info["count"], "resources": info["resources"]},
                ))

        except sh.exceptions.InvalidAccessException:
            # Security Hub not enabled
            findings.append(Finding(
                skill=self.name,
                title="Security Hub not enabled",
                severity=Severity.INFO, region=region,
                description="Enable Security Hub to get automated security checks across CIS, FSBP, PCI-DSS",
                recommended_action="Enable Security Hub in the AWS console",
            ))
        except Exception:
            pass
        return findings
