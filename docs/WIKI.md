# AWS Ops Agent — Complete Guide

## What Is It?

AWS Ops Agent is like having a cloud operations expert watching your AWS account 24/7. It automatically scans your entire AWS environment — every region, every service — and tells you exactly what needs attention: where you're wasting money, where your security has gaps, where your infrastructure is fragile, and what's about to break.

Think of it as a health checkup for your AWS account. You press one button, and within a minute you get a complete picture of your cloud health across cost, security, compliance, resiliency, and operations.

It also fixes things. Found an orphaned EBS volume burning $8/month? One click to delete it. Open security group exposing port 22 to the internet? One click to lock it down. Missing tags on your resources? One click to apply them. 18 common issues can be fixed without leaving the dashboard.

And if you're not sure what to do, there's an AI chat assistant built in. It knows your scan results and can walk you through what to prioritize, explain what a finding means in plain English, and guide you through fixing things step by step.

---

## Architecture

The system has four deployment modes, from simplest to most enterprise-ready:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     HOW CUSTOMERS USE IT                            │
│                                                                     │
│  Mode 1: Web Dashboard (localhost or ECS Fargate)                  │
│  ┌──────────┐     ┌──────────────────────────────────────────┐     │
│  │ Browser  │────▶│ FastAPI Server (:8080)                    │     │
│  └──────────┘     │  ├── 12 Scanning Skills (parallel)       │     │
│                   │  ├── 18 Fix It Remediations               │     │
│                   │  ├── AI Chat (Bedrock Claude)             │     │
│                   │  └── Security Middleware                   │     │
│                   └──────────────────────────────────────────┘     │
│                                                                     │
│  Mode 2: MCP Server (for Kiro, Claude Desktop, Q Developer)       │
│  ┌──────────┐     ┌──────────────────────────────────────────┐     │
│  │ MCP      │────▶│ FastMCP Server (stdio/SSE)                │     │
│  │ Client   │     │  └── 16 Tools (12 scans + remediate +    │     │
│  └──────────┘     │       list_skills + get_account_info +    │     │
│                   │       scan_all)                            │     │
│                   └──────────────────────────────────────────┘     │
│                                                                     │
│  Mode 3: Strands Agent (interactive CLI)                           │
│  ┌──────────┐     ┌──────────────────────────────────────────┐     │
│  │ Terminal │────▶│ Strands Agent                              │     │
│  │ (chat)   │     │  ├── Bedrock Claude (reasoning)           │     │
│  └──────────┘     │  └── MCP Server (subprocess)              │     │
│                   │       └── 16 Tools                         │     │
│                   └──────────────────────────────────────────┘     │
│                                                                     │
│  Mode 4: Bedrock AgentCore (managed, production)                   │
│  ┌──────────┐     ┌──────────┐     ┌─────────────────────────┐    │
│  │ App/API  │────▶│ AgentCore│────▶│ Strands Agent Container  │    │
│  │          │     │ Gateway  │     │  ├── Bedrock Claude       │    │
│  └──────────┘     └──────────┘     │  └── MCP Server + Skills  │    │
│                                    └─────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘

All modes use the same 12 skills scanning the same AWS services:

┌─────────────────────────────────────────────────────────────────────┐
│                     AWS SERVICES SCANNED                            │
│                                                                     │
│  Compute: EC2, Lambda, ECS, SageMaker                              │
│  Database: RDS, DynamoDB                                            │
│  Storage: S3, EBS                                                   │
│  Network: VPC, ELB, NAT Gateway, CloudFront, API Gateway           │
│  Security: GuardDuty, Security Hub, IAM                            │
│  Operations: CloudWatch, CloudTrail, AWS Config, Health             │
│  Cost: Cost Explorer, Service Quotas, Trusted Advisor              │
│  Messaging: SQS, SNS                                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Language | Python 3.10+ | Universal, great AWS SDK support |
| Web Framework | FastAPI | Async, fast, auto-docs |
| AI Model | Amazon Bedrock (Claude Haiku 4.5) | Low latency, cost-effective, tool-use support |
| Agent Framework | Strands Agents SDK | AWS-native, MCP integration, Bedrock-optimized |
| MCP Server | FastMCP | Simple tool registration, stdio + SSE transport |
| AWS SDK | Boto3 | Official AWS Python SDK |
| CLI | Click + Rich | Beautiful terminal output |
| Frontend | Vanilla JS + CSS | Zero build step, no npm needed |
| Diagrams | Mermaid.js | Architecture visualization in browser |
| Testing | Pytest (359 tests) | Full coverage, all mocked |
| Container | Docker (Python 3.12-slim) | Lightweight, production-ready |
| Deployment | CloudFormation / AgentCore | One-command deploy |

---

## The 12 Skills — What They Do and Why They Matter

### 💰 Cost-Anomaly
**What it does:** Compares this week's spending to last week, service by service. Flags any service with a 25%+ increase. Also checks AWS Cost Anomaly Detection for flagged anomalies and spots new services that appeared this month but weren't used last month.

**Why it matters:** Cost spikes often go unnoticed until the monthly bill arrives. A runaway test environment, an accidentally launched large instance, or a new service someone forgot about can add thousands to your bill. This skill catches it within days, not weeks.

**Example finding:** "Amazon SageMaker: +67% week-over-week — Last week: $1,200 | This week (projected): $2,004 | Change: +$804/week"

---

### 🧟 Zombie-Hunter
**What it does:** Finds resources that exist but aren't doing anything useful — unattached EBS volumes (no instance connected), unused Elastic IPs (not assigned to anything), NAT Gateways with zero traffic in 7 days, EC2 instances with less than 2% CPU over a week, and RDS databases with zero connections.

**Why it matters:** Gartner estimates 25% of cloud resources are idle or orphaned at any given time. These "zombie" resources silently burn money every hour. A single forgotten NAT Gateway costs $32/month. An idle m5.xlarge costs $140/month. Across an organization with dozens of accounts, this adds up to tens of thousands per year.

**Example finding:** "Idle EC2: i-0abc123def456 — t3.large | CPU: 0.5% | $73/mo"

**Fix It:** Stop the instance with one click.

---

### 🛡️ Security-Posture
**What it does:** Pulls active GuardDuty findings (severity 4+), checks Security Hub for failed compliance controls (CIS, AWS Foundational), finds security groups open to 0.0.0.0/0 on dangerous ports (SSH 22, RDP 3389, MySQL 3306, Postgres 5432, MongoDB 27017), checks for S3 buckets with public ACLs, and flags IAM access keys older than 90 days.

**Why it matters:** IBM Security reports the average cost of a data breach reached $4.88M in 2024. Most breaches start with a misconfiguration — an open port, a public bucket, a stale access key. This skill surfaces those misconfigurations before they become incidents.

**Example finding:** "Open port 22 to 0.0.0.0/0: sg-0abc123 — SG 'default' allows inbound on port 22 from anywhere"

**Fix It:** Revoke the 0.0.0.0/0 rule with one click.

---

### 📊 Capacity-Planner
**What it does:** Checks EC2 on-demand instance quotas approaching their limits, finds On-Demand Capacity Reservations (ODCRs) that are underutilized (paying for capacity you're not using), and monitors SageMaker endpoints at max scaling capacity.

**Why it matters:** Service quota limits are one of the most common causes of unexpected production outages during scaling events. You try to launch instances during a traffic spike and hit a limit nobody knew about. This skill warns you before that happens.

**Example finding:** "Underutilized ODCR: cr-0abc123 — p4d.24xlarge | 2/10 used (20%) | 8 idle | $191,000/mo waste"

---

### 🔍 Event-Analysis
**What it does:** Scans CloudTrail for high-risk events in the last 24 hours — things like DeleteSecurityGroup, TerminateInstances, PutBucketPolicy, DeleteDBInstance. Flags root account usage (which should never happen in daily operations). Counts unauthorized API calls (AccessDenied errors) which may indicate misconfiguration or compromise. Checks AWS Config for non-compliant rules.

**Why it matters:** Early detection of anomalous activity is critical for security incident response. If someone deletes a security group or terminates instances, you want to know immediately — not when a customer reports an outage.

**Example finding:** "Root account activity: ConsoleLogin — Root account used at 2025-02-24T03:15:00Z"

---

### 🏗️ Resiliency-Gaps
**What it does:** Checks all 6 Well-Architected Framework pillars:
- **Reliability:** Single-AZ RDS (no failover), single-AZ load balancers, RDS with no backups, ASGs that can't scale (min=max)
- **Security:** Unencrypted EBS volumes, unencrypted RDS, VPCs without flow logs
- **Performance:** Old-generation instances (m4, c3, t2) that should be upgraded
- **Operational Excellence:** EC2 instances with no CloudWatch alarms, resources missing standard tags
- **Sustainability:** x86 instances eligible for Graviton migration (20% cost savings + better energy efficiency), oversized instances with <10% CPU

**Why it matters:** The Well-Architected Framework identifies single points of failure as the top reliability risk. A single-AZ RDS instance means one AZ outage takes down your database. No backups means one accidental delete loses everything. This skill finds those gaps before they cause incidents.

**Example finding:** "Single-AZ RDS: my-production-db — db.r5.large | postgres | No Multi-AZ failover"

**Fix It:** Enable Multi-AZ with one click.

---

### 🏷️ Tag-Enforcer
**What it does:** Scans EC2 instances, RDS databases, S3 buckets, and Lambda functions for three mandatory tags: Environment, Team, and Owner. Reports which resources are missing which tags.

**Why it matters:** AWS Well-Architected Framework recommends mandatory tagging as a foundation for cost allocation and operational governance. Without tags, you can't answer "which team owns this resource?" or "how much does the production environment cost?" Organizations with consistent tagging report 40% faster incident response times.

**Example finding:** "Untagged EC2: i-0abc123 — t3.micro | web-server | Missing: Environment, Team"

**Fix It:** Apply default tags with one click.

---

### ⏳ Lifecycle-Tracker
**What it does:** Flags Lambda functions running deprecated runtimes (Python 3.7, Node.js 16, Go 1.x, etc.), RDS databases on end-of-life engine versions (MySQL 5.7, PostgreSQL 11-13), and ECS Fargate services on old platform versions.

**Why it matters:** AWS deprecates runtimes on a regular cycle, and running unsupported versions means no security patches. A Lambda function on Python 3.7 (EOL December 2023) has over a year of unpatched vulnerabilities. This is a compliance risk that auditors will flag.

**Example finding:** "Deprecated runtime: my-function — python3.7 (EOL: 2023-12-04) — upgrade to python3.12"

**Fix It:** Upgrade the runtime with one click.

---

### 🏥 Health-Monitor
**What it does:** Pulls AWS Health events (service issues, scheduled maintenance, account notifications) from the last 7 days. Also checks Trusted Advisor for warnings and errors across cost, security, reliability, and performance categories.

**Why it matters:** AWS Health events provide advance notice of maintenance and service issues. Proactive monitoring can reduce mean-time-to-resolution by up to 60%. If AWS is doing maintenance on your RDS instance next Tuesday, you want to know now — not when it goes down.

**Example finding:** "⚠ Service issue: EC2 (open) — EC2 connectivity issues in us-east-1"

---

### 📏 Quota-Guardian
**What it does:** Monitors 12 key service quotas: EC2 on-demand instances, Elastic IPs, VPCs, Internet Gateways, NAT Gateways, ALBs, Lambda concurrent executions, RDS instances, S3 buckets, EBS storage, ECS clusters, and CloudFormation stacks. Alerts when usage exceeds 70% of the limit.

**Why it matters:** Hitting a service quota during a scaling event causes an outage that's hard to diagnose. "Why can't I launch more instances?" — because you hit your vCPU limit. This skill warns you before you hit the wall.

**Example finding:** "Quota 85%: Running On-Demand Standard instances — ec2 | Limit: 256 | Usage: 85%"

---

### 🏗️ Arch-Diagram
**What it does:** Discovers every resource in your account — EC2, RDS, Lambda, ECS, ELB, VPC, S3, API Gateway, DynamoDB, SQS, SNS, CloudFront — using both direct API calls and AWS Config relationships. Then sends that data to Amazon Bedrock (Claude) to generate a visual Mermaid architecture diagram showing how resources connect.

**Why it matters:** Understanding your full resource footprint is the first step to optimizing architecture. Most teams don't have an up-to-date architecture diagram. This skill generates one automatically from what's actually deployed — no manual drawing required.

---

### 🎯 CostOpt-Intelligence
**What it does:** Seven cost optimization checks:
1. **Savings Plan recommendations** — Compute SP vs EC2 Instance SP, 1-year vs 3-year, with projected monthly savings
2. **RI utilization & coverage** — Flags underutilized Reserved Instances and coverage gaps
3. **Right-sizing** — EC2 instances with <20% avg CPU and <50% max CPU over 14 days, with specific downsize recommendations
4. **EBS GP2→GP3 migration** — GP2 volumes that save 20% by switching to GP3 (no downtime, online migration)
5. **S3 Intelligent-Tiering** — Large Standard buckets that could save up to 40% on infrequently accessed data
6. **NAT Gateway data costs** — High-traffic NATs where VPC endpoints for S3/DynamoDB could reduce costs
7. **Expiring commitments** — Savings Plans and RIs expiring within 60 days

**Why it matters:** Flexera's 2024 State of the Cloud report estimates organizations waste 28% of their cloud spend. This skill tells you exactly where to optimize and how much you'll save — not just "you're spending too much" but "switch this instance from m5.4xlarge to m5.2xlarge and save $248/month."

**Example finding:** "SP opportunity: Compute SP (1-year) — save $1,200/mo | Commit $1.65/hr | Savings: 32%"

---

## Security Features

The dashboard includes multiple security layers:

- **API Key Authentication** — Required for non-localhost deployments
- **CORS Lockdown** — Restricted to localhost by default
- **Rate Limiting** — 60 requests/minute per IP with burst protection
- **Security Headers** — CSP, X-Frame-Options DENY, X-Content-Type-Options nosniff
- **Chat Guardrails** — Blocks prompt injection (12 patterns), topic boundary violations (6 patterns), and scrubs output for leaked system prompts or access keys
- **Input Validation** — Chat messages capped at 4000 characters, control characters stripped
- **Audit Logging** — Every remediation and chat request logged with timestamp and client IP

---

## Step-by-Step Installation Guide

### Option A: Run Locally (5 minutes)

**Prerequisites:** Python 3.9+, AWS CLI configured

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_ORG/aws-ops-agent.git
cd aws-ops-agent

# 2. Install
python3 -m pip install -e .

# 3. Launch the dashboard
python3 -m ops_agent.cli --profile your-profile dashboard

# 4. Open http://127.0.0.1:8080 in your browser
# 5. Click "Run All Skills" and wait ~60 seconds
```

### Option B: Docker (2 minutes)

```bash
git clone https://github.com/YOUR_ORG/aws-ops-agent.git
cd aws-ops-agent

# Run with your AWS credentials
AWS_PROFILE=your-profile docker compose up

# Open http://localhost:8080
```

### Option C: Deploy to AWS (ECS Fargate + ALB)

```bash
git clone https://github.com/YOUR_ORG/aws-ops-agent.git
cd aws-ops-agent

# Find your VPC and subnets
aws ec2 describe-vpcs --query 'Vpcs[].{Id:VpcId,Name:Tags[?Key==`Name`].Value|[0]}' --output table
aws ec2 describe-subnets --filters Name=vpc-id,Values=YOUR_VPC \
  --query 'Subnets[?MapPublicIpOnLaunch].{Id:SubnetId,AZ:AvailabilityZone}' --output table

# Deploy (creates ECR, builds image, deploys CloudFormation)
./deploy/deploy.sh --vpc vpc-xxx --subnets subnet-aaa,subnet-bbb --profile your-profile

# You'll get a public URL back in ~3 minutes
# To tear down: ./deploy/deploy.sh --destroy --profile your-profile
```

### Option D: Deploy to Bedrock AgentCore (production)

```bash
# 1. Install prerequisites
pip install bedrock-agentcore-starter-toolkit

# 2. Clone and install
git clone https://github.com/YOUR_ORG/aws-ops-agent.git
cd aws-ops-agent
pip install -e ".[agent]"

# 3. Configure AWS credentials
export AWS_PROFILE=your-profile
export AWS_REGION=us-east-1

# 4. Deploy to AgentCore
cd deploy/agentcore
agentcore configure --entrypoint agent.py
agentcore launch

# 5. Test
agentcore invoke '{"prompt": "Scan my account for security issues"}'
agentcore invoke '{"prompt": "What are my cost optimization opportunities?"}'
agentcore invoke '{"prompt": "Run all skills and give me a prioritized summary"}'
```

### Option E: Use as MCP Server (for Kiro, Claude Desktop, Q Developer)

Add to your MCP client config:

```json
{
  "mcpServers": {
    "aws-ops-agent": {
      "command": "python3",
      "args": ["-m", "ops_agent.mcp_server"],
      "env": { "AWS_PROFILE": "your-profile" }
    }
  }
}
```

Then ask your AI assistant: "Scan my AWS account for zombie resources"

### Option F: Interactive Strands Agent (CLI chat)

```bash
pip install -e ".[agent]"
python3 -m ops_agent.cli --profile your-profile agent
```

Chat naturally:
```
You: What's the security posture of my account?
You: Are there any idle resources wasting money?
You: Fix the open port 22 on sg-abc123
You: What Savings Plan should I buy?
```

---

## AWS Permissions Required

**For scanning (read-only):** The `ReadOnlyAccess` managed policy covers most skills. Key permissions: `ec2:Describe*`, `rds:Describe*`, `s3:List*`, `lambda:List*`, `cloudwatch:GetMetricStatistics`, `cloudtrail:LookupEvents`, `guardduty:GetFindings`, `securityhub:GetFindings`, `ce:GetCostAndUsage`, `bedrock:InvokeModel`.

**For remediation (write):** `ec2:DeleteVolume`, `ec2:StopInstances`, `ec2:RevokeSecurityGroupIngress`, `rds:ModifyDBInstance`, `s3:PutPublicAccessBlock`, `iam:UpdateAccessKey`, `lambda:UpdateFunctionConfiguration`, and a few more.

**For Bedrock chat:** `bedrock:InvokeModel` — enable Claude Haiku 4.5 in the Bedrock console.

---

## Configuration

All settings are via environment variables — no config files to manage:

| Variable | Default | What It Does |
|----------|---------|-------------|
| `OPS_AGENT_API_KEY` | _(none)_ | API key for dashboard auth |
| `OPS_AGENT_CORS_ORIGINS` | `localhost` | Allowed CORS origins |
| `OPS_AGENT_RATE_LIMIT` | `60` | Requests per minute per IP |
| `OPS_AGENT_BEDROCK_MODEL` | `claude-haiku-4.5` | Bedrock model for chat |
| `OPS_AGENT_BEDROCK_REGION` | `us-east-1` | Bedrock region |
| `OPS_AGENT_AUDIT_LOG` | `ops_agent_audit.log` | Audit log file |

---

## Testing

```bash
cd aws-ops-agent
python3 -m pytest tests/ -v
# 359 tests, all passing, ~1.3 seconds
```

Covers all 12 skills, all 18 remediations, all API endpoints, security middleware, chat guardrails, notifications, and core framework.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `command not found: ops-agent` | Use `python3 -m ops_agent.cli` instead |
| Bedrock chat not working | Enable Claude model in Bedrock console for us-east-1 |
| 401 on API calls | Pass `X-API-Key` header |
| 429 Too Many Requests | Rate limited — wait 60 seconds |
| Skills return no findings | Check AWS permissions — need ReadOnlyAccess minimum |
| Org scan fails | Verify cross-account role exists with correct trust policy |
