# AWS Ops Agent
### Autonomous Cloud Operations Dashboard


## Executive Summary

Managing AWS at scale is hard. Teams spend hours jumping between consoles, chasing down idle resources, triaging security alerts, and trying to make sense of cost spikes — often across dozens of accounts. The AWS Ops Agent brings all of that into one place with eleven scanning skills running in parallel, an AI chat assistant powered by Amazon Bedrock, one-click remediation, and org-wide visibility across all accounts.


## Solution Architecture

```
Browser (Dashboard SPA)
    │
    ▼
FastAPI Server
    ├──► 11 Scanning Skills (parallel via ThreadPoolExecutor) ──► AWS APIs
    ├──► Bedrock Claude Haiku 4.5 (Chat + Architecture Diagrams)
    ├──► AWS Organizations (Cross-Account Role Assumption)
    └──► Remediation Engine (16 automated fix actions)
```

**Deployment:** Single Python process. Local CLI, Docker container, or ECS Fargate behind ALB.

---

## Scanning Skills (11)

| Skill | What It Does |
|-------|-------------|
| **Cost-Anomaly** | Detects week-over-week spending spikes, flags new services, projects monthly impact |
| **Zombie-Hunter** | Finds idle EC2, unattached EBS, unused EIPs/NATs, idle RDS — resources burning money |
| **Security-Posture** | GuardDuty findings, Security Hub controls, open security groups, public S3, old IAM keys |
| **Capacity-Planner** | ODCR utilization, SageMaker capacity, EC2 quota headroom |
| **Event-Analysis** | CloudTrail high-risk events, root account usage, Config compliance |
| **Resiliency-Gaps** | All 6 WAF pillars: reliability, security, performance, ops excellence, sustainability |
| **Tag-Enforcer** | Finds untagged EC2, RDS, S3, Lambda — auto-applies mandatory tags |
| **Lifecycle-Tracker** | Deprecated Lambda runtimes, EOL RDS engines, old Fargate platforms |
| **Health-Monitor** | AWS Health events, scheduled maintenance, Trusted Advisor checks |
| **Quota-Guardian** | Service quotas approaching limits — prevents scaling outages |
| **Arch-Diagram** | Discovers all resources via Config/CloudTrail, generates visual Mermaid diagram via Bedrock |

---

## AI Chat Assistant

Powered by Claude Haiku 4.5 on Amazon Bedrock. It knows which skills have been run and references actual scan findings — never fabricates data. It can explain findings, recommend priorities, walk through remediation steps, and answer general AWS questions. Each skill includes a professional industry insight when results aren't yet available.

---

## One-Click Remediation (16 Actions)

Delete unattached EBS volumes, release unused EIPs, stop idle EC2/RDS, restrict open security groups, block public S3 access, deactivate old IAM keys, enable RDS Multi-AZ and backups, enable VPC Flow Logs, cancel underutilized ODCRs, apply mandatory tags to EC2/RDS/S3/Lambda. Every action requires explicit confirmation before execution.

---

## Sample Scenarios

### Scenario 1: Cost Optimization Review

A finance team asks: "Where is our cloud spend going?" The ops team runs Cost-Anomaly and Zombie-Hunter. Cost-Anomaly flags a 187% week-over-week spike in EC2 spend and a new Neptune service nobody approved. Zombie-Hunter finds 12 unattached EBS volumes ($96/mo) and 3 idle EC2 instances ($219/mo). The team clicks Fix It to delete the volumes and stop the idle instances, saving $315/month immediately.

### Scenario 2: Security Audit Preparation

Before a SOC2 audit, the security team runs Security-Posture. It surfaces 4 security groups open to 0.0.0.0/0 on port 22, 2 public S3 buckets, and 8 IAM access keys older than 90 days. The team restricts the security groups and blocks public S3 access with one click each. They ask the chat assistant: "Which of these findings would fail a SOC2 audit?" and get a prioritized list with control references.

### Scenario 3: Multi-Account Org Health Check

A platform team managing 50 accounts runs an org-wide scan. The dashboard groups findings by OU — Production has 3 critical findings (single-AZ RDS with no backups), Development has 45 zombie resources wasting $2,100/month, and Security OU is clean. The team drills into Production, enables Multi-AZ and backups on the critical databases, and exports the report for leadership.

### Scenario 4: Deprecated Runtime Cleanup

A developer runs Lifecycle-Tracker and discovers 15 Lambda functions still on Python 3.8 (EOL October 2024) and 2 RDS instances on MySQL 5.7 (EOL). The chat assistant explains the security implications and provides upgrade paths. The team plans a sprint to migrate the functions to Python 3.12.

### Scenario 5: Architecture Discovery

A new team member needs to understand the production environment. They run Arch-Diagram, which discovers 23 EC2 instances, 4 RDS databases, 12 Lambda functions, 3 ECS clusters, 2 ALBs, and 8 VPCs. Bedrock generates a visual Mermaid diagram showing the actual connections between resources based on AWS Config relationships and CloudTrail data. No manual drawing needed.

### Scenario 6: Tag Governance

The FinOps team mandates Environment, Team, and Owner tags on all resources. They run Tag-Enforcer across the org and find 67% of resources are missing at least one mandatory tag. They click Fix It to apply default placeholder tags, then work with teams to update them to real values. Cost allocation accuracy improves from 40% to 95%.

---

## Deployment Options

| Method | Command |
|--------|---------|
| **Local** | `ops-agent --profile your-profile dashboard` |
| **Docker** | `docker run -p 8080:8080 -v ~/.aws:/root/.aws ops-agent-dashboard` |
| **AWS (ECS Fargate)** | CDK/CloudFormation template with ALB + IAM task role |

---

## Customer Value

- Single pane of glass for cloud operations across all accounts and regions
- Reduces mean-time-to-remediation from hours to seconds
- Catches cost waste that typically accounts for 25-30% of cloud spend
- Surfaces security misconfigurations before they become incidents
- Provides audit-ready visibility into compliance posture
- Democratizes cloud operations with an AI assistant that any team member can use
- Generates architecture diagrams from real infrastructure — no manual effort
