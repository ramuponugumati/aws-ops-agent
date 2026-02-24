# ⚡🔧 AWS Ops Agent

Autonomous cloud operations agent with a web dashboard. Scans your AWS environment for cost waste, security risks, resiliency gaps, deprecated resources, and more — then helps you fix them.

## Features

- **11 scanning skills** running in parallel across all regions
- **Web dashboard** with real-time findings, severity filtering, and one-click remediation
- **AI chat assistant** powered by Amazon Bedrock (Claude) with live AWS infrastructure queries
- **18 one-click Fix It actions** with confirmation — delete orphaned volumes, restrict open SGs, enable backups, apply tags, and more
- **Org-wide scanning** across all accounts via cross-account role assumption
- **Chat guardrails** — prompt injection protection, topic boundaries, output sanitization
- **Security hardened** — API key auth, rate limiting, CORS lockdown, security headers, audit logging
- **340 unit tests** covering all skills, remediations, API endpoints, and security middleware

## Quick Start

### Option 1: Local (fastest)

```bash
git clone https://github.com/YOUR_ORG/aws-ops-agent.git
cd aws-ops-agent
pip install -e .
ops-agent --profile your-profile dashboard
```

Opens http://127.0.0.1:8080 in your browser.

### Option 2: Docker Compose

```bash
git clone https://github.com/YOUR_ORG/aws-ops-agent.git
cd aws-ops-agent
AWS_PROFILE=your-profile docker compose up
```

Opens at http://localhost:8080.

### Option 3: Deploy to AWS (ECS Fargate + ALB)

One command deploys everything — ECR repo, Docker image, ECS cluster, Fargate service, ALB:

```bash
./deploy/deploy.sh \
  --vpc vpc-xxxxxxxx \
  --subnets subnet-aaaa,subnet-bbbb \
  --profile your-profile \
  --region us-east-1
```

You'll get a public URL back in about 3 minutes. To tear down:

```bash
./deploy/deploy.sh --destroy --profile your-profile --region us-east-1
```

**Find your VPC and subnets:**
```bash
# List VPCs
aws ec2 describe-vpcs --query 'Vpcs[].{Id:VpcId,Name:Tags[?Key==`Name`].Value|[0]}' --output table

# List public subnets in a VPC
aws ec2 describe-subnets --filters Name=vpc-id,Values=YOUR_VPC_ID \
  --query 'Subnets[?MapPublicIpOnLaunch].{Id:SubnetId,AZ:AvailabilityZone}' --output table
```

## Prerequisites

- Python 3.9+
- AWS credentials configured (profile, env vars, or IAM role)
- Amazon Bedrock model access for chat (Claude Haiku 4.5)
- Docker (for container deployment)

## Skills

| Skill | Icon | Description |
|-------|------|-------------|
| Cost-Anomaly | 💰 | Detect cost spikes, week-over-week changes, new services |
| Zombie-Hunter | 🧟 | Find idle EC2, unattached EBS, unused EIPs/NATs |
| Security-Posture | 🛡️ | GuardDuty, Security Hub, open ports, public S3, old IAM keys |
| Capacity-Planner | 📊 | ODCR utilization, SageMaker capacity, EC2 quotas |
| Event-Analysis | 🔍 | CloudTrail high-risk events, Config compliance, root usage |
| Resiliency-Gaps | 🏗️ | All 6 Well-Architected pillars: reliability, security, performance, ops, sustainability |
| Tag-Enforcer | 🏷️ | Find untagged EC2, RDS, S3, Lambda — auto-apply mandatory tags |
| Lifecycle-Tracker | ⏳ | Deprecated Lambda runtimes, EOL RDS engines, old Fargate platforms |
| Health-Monitor | 🏥 | AWS Health events, Trusted Advisor checks |
| Quota-Guardian | 📏 | Service quotas approaching limits |
| Arch-Diagram | 🏗️ | Discover resources and generate architecture maps via Bedrock |

## One-Click Remediation (18 actions)

| Finding | Fix It Action |
|---------|---------------|
| Unattached EBS volume | Delete volume |
| Unused Elastic IP | Release EIP |
| Unused NAT Gateway | Delete NAT |
| Idle EC2 instance | Stop instance |
| Idle RDS instance | Stop instance |
| Open port to 0.0.0.0/0 | Revoke SG ingress rule |
| Public S3 bucket | Enable Block Public Access |
| Old IAM access key | Deactivate key |
| Single-AZ RDS | Enable Multi-AZ |
| RDS no backups | Enable 7-day backup retention |
| No VPC Flow Logs | Enable flow logs to CloudWatch |
| Underutilized ODCR | Cancel capacity reservation |
| Untagged EC2/RDS/S3/Lambda | Apply mandatory tags |
| Deprecated Lambda runtime | Upgrade runtime |
| EOL RDS engine | Schedule engine upgrade |

## CLI Usage

```bash
# Run all skills
ops-agent --profile your-profile run

# Run a specific skill
ops-agent --profile your-profile run --skill zombie-hunter

# Org-wide scan
ops-agent --profile your-profile org-scan --role OrganizationAccountAccessRole

# Export results to JSON
ops-agent --profile your-profile run --export results.json

# List available skills
ops-agent skills
```

## Chat Assistant

The chat tab uses Amazon Bedrock (Claude Haiku 4.5) with built-in guardrails:
- Analyzes your scan findings and recommends priorities
- Walks through remediation steps with confirmation
- Answers general AWS questions
- **Prompt injection protection** — blocks system prompt override attempts, role-play, delimiter injection
- **Topic boundaries** — blocks harmful content, credential extraction, PII requests
- **Output sanitization** — scrubs leaked system prompts and redacts access key patterns

Requires Bedrock model access enabled in your account.

## Security

The dashboard includes multiple security layers:

| Feature | Detail |
|---------|--------|
| API Key Auth | Required for non-localhost deployments (`X-API-Key` header) |
| CORS | Locked to localhost by default, configurable via `OPS_AGENT_CORS_ORIGINS` |
| Rate Limiting | 60 req/min per IP, burst protection |
| Security Headers | CSP, X-Frame-Options DENY, X-Content-Type-Options, Referrer-Policy |
| Chat Guardrails | Prompt injection detection, topic boundaries, output sanitization |
| Audit Logging | All remediations and chat requests logged to `ops_agent_audit.log` |
| Input Validation | Chat messages capped at 4000 chars, control chars stripped |

## Configuration (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `OPS_AGENT_API_KEY` | _(none)_ | API key for auth (auto-generated for non-localhost) |
| `OPS_AGENT_CORS_ORIGINS` | `http://127.0.0.1:8080,http://localhost:8080` | Allowed CORS origins |
| `OPS_AGENT_RATE_LIMIT` | `60` | Requests per minute per IP |
| `OPS_AGENT_RATE_BURST` | `15` | Burst limit (requests per 5 seconds) |
| `OPS_AGENT_BEDROCK_MODEL` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Bedrock model ID |
| `OPS_AGENT_BEDROCK_REGION` | `us-east-1` | Bedrock region |
| `OPS_AGENT_AUDIT_LOG` | `ops_agent_audit.log` | Audit log file path |

## Testing

```bash
pip install -e ".[test]"
python -m pytest tests/ -v
```

340 tests covering all skills, remediations, API endpoints, security middleware, and chat guardrails.

## AWS Permissions

**Minimum for scanning:** `ReadOnlyAccess` managed policy covers most skills.

**For remediation**, the task role needs these additional permissions:
- `ec2:DeleteVolume`, `ec2:ReleaseAddress`, `ec2:StopInstances`, `ec2:RevokeSecurityGroupIngress`, `ec2:CreateTags`, `ec2:CreateFlowLogs`
- `rds:StopDBInstance`, `rds:ModifyDBInstance`, `rds:AddTagsToResource`
- `s3:PutPublicAccessBlock`, `s3:PutBucketTagging`
- `iam:UpdateAccessKey`
- `lambda:UpdateFunctionConfiguration`, `lambda:TagResource`
- `bedrock:InvokeModel` (for chat and arch diagrams)

**For org-wide scanning:** `sts:AssumeRole` + a cross-account role in each member account.

## Architecture

```
Browser → ALB → ECS Fargate → FastAPI Server
                                  ├── 11 Scanning Skills (parallel, multi-region)
                                  ├── Remediation Engine (18 actions)
                                  ├── Chat Handler → Amazon Bedrock (Claude)
                                  └── Job Store (in-memory)
```

See [ARCHITECTURE_DIAGRAM.md](ARCHITECTURE_DIAGRAM.md) for the full Mermaid diagram.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ops-agent` command not found | Run `pip install -e .` from the project root |
| Missing credentials | Run `aws configure` or set `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` |
| Bedrock chat not working | Enable Claude model access in the Bedrock console |
| Port in use | Use `--port 9090` or kill the existing process |
| Org scan fails | Verify cross-account role exists and trust policy is correct |
| 401 on API calls | Pass `X-API-Key` header (check terminal output for the key) |
| 429 Too Many Requests | Rate limit hit — wait 60 seconds |
