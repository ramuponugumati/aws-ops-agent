# AWS Ops Agent — Internal Wiki

## Overview

AWS Ops Agent is an autonomous cloud operations platform that scans AWS environments for cost waste, security risks, resiliency gaps, deprecated resources, and operational issues. It provides a web dashboard with real-time findings, one-click remediation, an AI chat assistant, and org-wide scanning across all accounts.

**Author:** Ramu Ponu
**Version:** 0.3.0
**Repository:** `aws-ops-agent/`

---

## Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.9+ |
| Web Framework | FastAPI | 0.100+ |
| ASGI Server | Uvicorn | 0.23+ |
| CLI Framework | Click | 8.0+ |
| CLI Rendering | Rich | 13.0+ |
| AWS SDK | Boto3 | 1.28+ |
| AI/Chat | Amazon Bedrock (Claude Haiku 4.5) | - |
| Scheduling | APScheduler | 3.10+ |
| HTTP Client | Requests | 2.28+ |
| Frontend | Vanilla JS + HTML + CSS | - |
| Diagramming | Mermaid.js (CDN) | 11.x |
| Testing | Pytest + Hypothesis + HTTPX | - |
| Container | Docker (Python 3.12-slim) | - |
| Infrastructure | CloudFormation (ECS Fargate + ALB) | - |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser / CLI                         │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────────┐
│                    FastAPI Server (:8080)                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ Security  │ │   Rate   │ │  CORS    │ │  API Key Auth │  │
│  │ Headers   │ │ Limiter  │ │ Lockdown │ │  Middleware    │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────┘  │
│                                                              │
│  API Endpoints:                                              │
│  ├── GET  /api/health          Health check                  │
│  ├── GET  /api/skills          List 12 skills                │
│  ├── POST /api/scan/{skill}    Run single skill              │
│  ├── POST /api/scan-all        Run all skills in parallel    │
│  ├── POST /api/org-scan        Org-wide cross-account scan   │
│  ├── POST /api/remediate       Execute Fix It action         │
│  ├── POST /api/chat            AI chat (Bedrock Claude)      │
│  ├── GET  /api/jobs/{id}       Job status                    │
│  └── GET  /api/jobs/{id}/results  Scan results               │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              12 Scanning Skills (Parallel)              │  │
│  │  💰 Cost-Anomaly    🧟 Zombie-Hunter   🛡️ Security     │  │
│  │  📊 Capacity        🔍 Event-Analysis  🏗️ Resiliency   │  │
│  │  🏷️ Tag-Enforcer    ⏳ Lifecycle       🏥 Health        │  │
│  │  📏 Quota-Guardian  🏗️ Arch-Diagram   🎯 CostOpt-Intel │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Remediation  │  │ Chat Handler │  │   Job Store      │  │
│  │ 18 Fix Its   │  │ + Guardrails │  │   (In-Memory)    │  │
│  └──────────────┘  └──────┬───────┘  └──────────────────┘  │
└──────────────────────────┬┼─────────────────────────────────┘
                           ││
              ┌────────────▼┼────────────────┐
              │      Amazon Bedrock          │
              │   Claude Haiku 4.5           │
              │   (Chat + Arch Diagrams)     │
              └──────────────────────────────┘
              
              ┌──────────────────────────────┐
              │     AWS Services Scanned     │
              │  EC2, RDS, S3, Lambda, ECS,  │
              │  VPC, IAM, CloudWatch,       │
              │  CloudTrail, Config,         │
              │  GuardDuty, Security Hub,    │
              │  Health, Trusted Advisor,    │
              │  Service Quotas, Cost        │
              │  Explorer, DynamoDB, SQS,    │
              │  SNS, API Gateway,           │
              │  CloudFront                  │
              └──────────────────────────────┘
```

---

## Project Structure

```
aws-ops-agent/
├── ops_agent/
│   ├── __init__.py
│   ├── core.py                 # Finding, SkillResult, SkillRegistry, BaseSkill
│   ├── cli.py                  # Click CLI: run, dashboard, org-scan, skills
│   ├── aws_client.py           # Boto3 helpers, parallel_regions, org tree
│   ├── notify.py               # Slack, SNS, console notifications
│   ├── skills/
│   │   ├── __init__.py         # Auto-registers all 12 skills
│   │   ├── cost_anomaly.py     # Week-over-week, anomaly detection, new services
│   │   ├── zombie_hunter.py    # Idle EC2/RDS, unattached EBS, unused EIP/NAT
│   │   ├── security_posture.py # GuardDuty, Security Hub, open SGs, public S3, IAM
│   │   ├── capacity_planner.py # EC2 quotas, ODCR utilization, SageMaker capacity
│   │   ├── event_analysis.py   # CloudTrail high-risk events, root usage, Config
│   │   ├── resiliency_gaps.py  # All 6 WAF pillars (12 checks)
│   │   ├── tag_enforcer.py     # Untagged EC2, RDS, S3, Lambda
│   │   ├── lifecycle_tracker.py# Deprecated runtimes, EOL engines, old Fargate
│   │   ├── health_monitor.py   # AWS Health events, Trusted Advisor
│   │   ├── quota_guardian.py   # Service quotas approaching limits
│   │   ├── arch_diagram.py     # Resource discovery + Bedrock Mermaid diagrams
│   │   └── costopt_intelligence.py # SP/RI recs, right-sizing, EBS/S3 optimization
│   └── dashboard/
│       ├── server.py           # FastAPI app with security middleware
│       ├── chat.py             # Bedrock Claude integration + guardrails
│       ├── guardrails.py       # Prompt injection, topic boundaries, output sanitization
│       ├── security.py         # API key auth, rate limiting, security headers, audit
│       ├── remediation.py      # 18 Fix It handlers
│       ├── jobs.py             # In-memory job store
│       └── static/
│           ├── index.html
│           ├── css/styles.css
│           ├── js/api.js, app.js, components.js
│           └── img/ops-agent.svg, costopt-intelligence.svg
├── tests/                      # 359 unit tests
│   ├── conftest.py
│   ├── test_core.py
│   ├── test_aws_client.py
│   ├── test_chat.py
│   ├── test_guardrails.py
│   ├── test_security.py
│   ├── test_server.py
│   ├── test_jobs.py
│   ├── test_notify.py
│   ├── test_remediation.py
│   ├── test_skill_registration.py
│   └── test_skill_*.py         # One per skill
├── deploy/
│   ├── deploy.sh               # One-click ECS Fargate deployment
│   └── cloudformation.yaml     # Full CFN template
├── Dockerfile
├── docker-compose.yml
├── setup.py
├── SECURITY_REVIEW.md
└── README.md
```

---

## Skills Reference

| # | Skill | Icon | What It Scans | AWS APIs Used |
|---|-------|------|---------------|---------------|
| 1 | cost-anomaly | 💰 | Spending spikes, week-over-week changes, new services | Cost Explorer, Cost Anomaly Detection |
| 2 | zombie-hunter | 🧟 | Idle EC2/RDS, unattached EBS, unused EIPs/NATs | EC2, RDS, CloudWatch |
| 3 | security-posture | 🛡️ | GuardDuty findings, Security Hub controls, open SGs, public S3, old IAM keys | GuardDuty, Security Hub, EC2, S3, IAM |
| 4 | capacity-planner | 📊 | EC2 quotas, ODCR utilization, SageMaker capacity | Service Quotas, EC2, SageMaker |
| 5 | event-analysis | 🔍 | High-risk CloudTrail events, root usage, unauthorized calls, Config compliance | CloudTrail, Config |
| 6 | resiliency-gaps | 🏗️ | All 6 WAF pillars: reliability, security, performance, ops, sustainability | EC2, RDS, ELB, VPC, CloudWatch, ASG |
| 7 | tag-enforcer | 🏷️ | Untagged EC2, RDS, S3, Lambda (mandatory: Environment, Team, Owner) | EC2, RDS, S3, Lambda |
| 8 | lifecycle-tracker | ⏳ | Deprecated Lambda runtimes, EOL RDS engines, old Fargate platforms | Lambda, RDS, ECS |
| 9 | health-monitor | 🏥 | AWS Health events, Trusted Advisor checks | Health, Support |
| 10 | quota-guardian | 📏 | 12 key service quotas approaching limits | Service Quotas, CloudWatch |
| 11 | arch-diagram | 🏗️ | Full resource discovery + Mermaid architecture diagram via Bedrock | Config, CloudTrail, EC2, RDS, Lambda, ECS, VPC, S3, DynamoDB, SQS, SNS, API GW, CloudFront |
| 12 | costopt-intelligence | 🎯 | Savings Plan/RI recommendations, right-sizing, GP2→GP3, S3 tiering, NAT data costs, expiring commitments | Cost Explorer, EC2, CloudWatch, S3 |

---

## One-Click Remediation (18 Actions)

| Finding | Action | AWS API Call |
|---------|--------|-------------|
| Unattached EBS | Delete volume | `ec2:DeleteVolume` |
| Unused EIP | Release address | `ec2:ReleaseAddress` |
| Unused NAT GW | Delete NAT | `ec2:DeleteNatGateway` |
| Idle EC2 | Stop instance | `ec2:StopInstances` |
| Idle RDS | Stop instance | `rds:StopDBInstance` |
| Open port 0.0.0.0/0 | Revoke SG rule | `ec2:RevokeSecurityGroupIngress` |
| Public S3 bucket | Block public access | `s3:PutPublicAccessBlock` |
| Old IAM key | Deactivate key | `iam:UpdateAccessKey` |
| Single-AZ RDS | Enable Multi-AZ | `rds:ModifyDBInstance` |
| No RDS backups | Enable 7-day retention | `rds:ModifyDBInstance` |
| No VPC Flow Logs | Enable flow logs | `ec2:CreateFlowLogs` |
| Underutilized ODCR | Cancel reservation | `ec2:CancelCapacityReservation` |
| Untagged EC2 | Apply tags | `ec2:CreateTags` |
| Untagged RDS | Apply tags | `rds:AddTagsToResource` |
| Untagged S3 | Apply tags | `s3:PutBucketTagging` |
| Untagged Lambda | Apply tags | `lambda:TagResource` |
| Deprecated runtime | Upgrade runtime | `lambda:UpdateFunctionConfiguration` |
| EOL RDS engine | Schedule upgrade | `rds:ModifyDBInstance` |

---

## Security Features

| Layer | Feature | Detail |
|-------|---------|--------|
| Auth | API Key | `X-API-Key` header, auto-generated for non-localhost |
| Network | CORS | Locked to localhost, configurable via `OPS_AGENT_CORS_ORIGINS` |
| Rate Limit | Per-IP | 60 req/min, burst protection (15/5sec) |
| Headers | CSP, X-Frame-Options | DENY framing, strict CSP, nosniff, referrer policy |
| Chat Input | Sanitization | 4000 char limit, control char stripping |
| Chat Input | Guardrails | Prompt injection detection (12 patterns), topic boundaries (6 patterns) |
| Chat Output | Sanitization | System prompt leak scrubbing, access key redaction |
| Audit | Logging | All remediations + chat requests logged to `ops_agent_audit.log` |

---

## Prerequisites

1. **Python 3.9+** — macOS: `brew install python@3.12` or use system Python
2. **AWS CLI configured** — `aws configure --profile your-profile`
3. **AWS permissions** — `ReadOnlyAccess` for scanning, specific write permissions for remediation (see IAM section below)
4. **Amazon Bedrock access** — Enable Claude Haiku 4.5 model in the Bedrock console (us-east-1)
5. **Docker** (optional) — For container deployment

---

## Installation

### Local Development

```bash
# Clone the repo
git clone <repo-url>
cd aws-ops-agent

# Install in editable mode
python3 -m pip install -e .

# Verify
python3 -m ops_agent.cli skills
```

### Launch Dashboard

```bash
# Using the module directly (always works)
python3 -m ops_agent.cli --profile your-profile dashboard

# Or if PATH includes pip bin directory
ops-agent --profile your-profile dashboard
```

Opens http://127.0.0.1:8080

### Docker

```bash
# Build and run
docker compose up

# Or manually
docker build -t ops-agent .
docker run -p 8080:8080 -v ~/.aws:/root/.aws:ro -e AWS_PROFILE=your-profile ops-agent
```

### Deploy to AWS (ECS Fargate + ALB)

```bash
# One command — creates ECR, builds image, deploys CFN stack
./deploy/deploy.sh \
  --vpc vpc-xxxxxxxx \
  --subnets subnet-aaaa,subnet-bbbb \
  --profile your-profile \
  --region us-east-1

# Tear down
./deploy/deploy.sh --destroy --profile your-profile --region us-east-1
```

---

## How Others Can Access

### Option 1: Run Locally (Individual Use)

Each person clones the repo and runs locally with their own AWS profile:

```bash
git clone <repo-url>
cd aws-ops-agent
python3 -m pip install -e .
python3 -m ops_agent.cli --profile their-profile dashboard
```

### Option 2: Shared Deployment (Team Use)

Deploy once to ECS Fargate using the deploy script. The ALB gives a public URL that anyone on the network can access. The ECS task role provides the AWS permissions — no individual credentials needed.

```
Team member → Browser → ALB URL → ECS Fargate → AWS APIs
```

Share the ALB URL + API key with the team.

### Option 3: Docker on a Shared Server

Run the Docker container on a shared EC2 instance or dev server:

```bash
docker run -d -p 8080:8080 \
  -e AWS_ACCESS_KEY_ID=AKIA... \
  -e AWS_SECRET_ACCESS_KEY=... \
  -e AWS_DEFAULT_REGION=us-east-1 \
  ops-agent
```

Access at `http://<server-ip>:8080`

---

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `OPS_AGENT_API_KEY` | _(none)_ | API key for auth |
| `OPS_AGENT_CORS_ORIGINS` | `http://127.0.0.1:8080,http://localhost:8080` | Allowed CORS origins |
| `OPS_AGENT_RATE_LIMIT` | `60` | Requests per minute per IP |
| `OPS_AGENT_RATE_BURST` | `15` | Burst limit |
| `OPS_AGENT_BEDROCK_MODEL` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Bedrock model ID |
| `OPS_AGENT_BEDROCK_REGION` | `us-east-1` | Bedrock region |
| `OPS_AGENT_AUDIT_LOG` | `ops_agent_audit.log` | Audit log path |

---

## IAM Permissions

### Minimum for Scanning (Read-Only)

The `ReadOnlyAccess` managed policy covers most skills. Key permissions:

```
ec2:Describe*, rds:Describe*, s3:List*, s3:GetBucket*,
lambda:List*, lambda:GetFunction, ecs:List*, ecs:Describe*,
elasticloadbalancing:Describe*, iam:List*, iam:GetUser,
cloudwatch:GetMetricStatistics, cloudwatch:DescribeAlarms,
cloudtrail:LookupEvents, config:Describe*, config:List*,
guardduty:List*, guardduty:GetFindings, securityhub:GetFindings,
health:Describe*, support:DescribeTrustedAdvisor*,
ce:GetCostAndUsage, ce:GetAnomalies, ce:GetSavingsPlansPurchaseRecommendation,
ce:GetReservationUtilization, ce:GetReservationCoverage,
service-quotas:GetServiceQuota, service-quotas:ListServiceQuotas,
organizations:List*, sts:GetCallerIdentity, sts:AssumeRole,
bedrock:InvokeModel
```

### Additional for Remediation (Write)

```
ec2:DeleteVolume, ec2:ReleaseAddress, ec2:DeleteNatGateway,
ec2:StopInstances, ec2:RevokeSecurityGroupIngress,
ec2:CreateTags, ec2:CreateFlowLogs, ec2:CancelCapacityReservation,
rds:StopDBInstance, rds:ModifyDBInstance, rds:AddTagsToResource,
s3:PutPublicAccessBlock, s3:PutBucketTagging,
iam:UpdateAccessKey,
lambda:UpdateFunctionConfiguration, lambda:TagResource
```

### For Org-Wide Scanning

Requires `sts:AssumeRole` and a cross-account role (`OrganizationAccountAccessRole`) in each member account with the above permissions.

---

## Testing

```bash
# Run all 359 tests
python3 -m pytest tests/ -v

# Run specific test file
python3 -m pytest tests/test_skill_costopt_intelligence.py -v

# Run with coverage
python3 -m pytest tests/ --cov=ops_agent --cov-report=term-missing
```

Test coverage:
- All 12 skills (scan logic, finding generation, severity mapping, edge cases)
- All 18 remediation handlers (success + failure + edge cases)
- All API endpoints (scan, remediate, chat, jobs, org-scan, health)
- Security middleware (API key auth, rate limiting, input validation)
- Chat guardrails (77 test cases: prompt injection, topic boundaries, output sanitization)
- Notifications (Slack, SNS)
- Core framework (Finding, SkillResult, SkillRegistry)

---

## CLI Reference

```bash
# Launch dashboard
python3 -m ops_agent.cli --profile PROFILE dashboard [--host HOST] [--port PORT] [--api-key KEY]

# Run all skills (CLI output)
python3 -m ops_agent.cli --profile PROFILE run [--skill SKILL] [--export FILE.json]

# Org-wide scan
python3 -m ops_agent.cli --profile PROFILE org-scan [--role ROLE] [--skill SKILL]

# List skills
python3 -m ops_agent.cli skills

# With notifications
python3 -m ops_agent.cli --profile PROFILE run --slack-webhook URL --sns-topic ARN
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `command not found: ops-agent` | Use `python3 -m ops_agent.cli` instead, or add `~/Library/Python/3.9/bin` to PATH |
| Missing credentials | `aws configure --profile your-profile` |
| Bedrock chat not working | Enable Claude model in Bedrock console for us-east-1 |
| Port 8080 in use | `--port 9090` |
| 401 Unauthorized | Pass `X-API-Key` header (check terminal for the key) |
| 429 Too Many Requests | Rate limited — wait 60 seconds |
| Org scan fails | Verify cross-account role exists with correct trust policy |
| Static files not updating | Restart server — cache version is bumped in index.html |

---

## Changelog

### v0.3.0 (Current)
- Added CostOpt Intelligence skill (Savings Plans, RI, right-sizing, EBS/S3 optimization)
- Security hardening: API key auth, CORS lockdown, rate limiting, security headers
- Chat guardrails: prompt injection protection, topic boundaries, output sanitization
- Audit logging for all remediations and chat requests
- 359 unit tests
- One-click ECS Fargate deployment (CloudFormation + deploy script)
- Docker Compose support
- Health check endpoint (`/api/health`)
- Configurable Bedrock model via environment variable

### v0.2.0
- 11 scanning skills
- Web dashboard with real-time findings
- AI chat assistant (Bedrock Claude)
- 18 one-click Fix It actions
- Org-wide scanning
- CLI with JSON export
- Slack and SNS notifications
