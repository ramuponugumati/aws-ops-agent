# AWS Ops Agent — AI Agent for Cloud Operations

## What Is It?

AWS Ops Agent is an AI-powered cloud operations agent that you can talk to in natural language. Ask it to scan your AWS account, find security issues, identify cost waste, check resiliency gaps — and it figures out which tools to use, runs them, and presents the results.

It's built on [Strands Agents SDK](https://strandsagents.com/) with [Amazon Bedrock](https://aws.amazon.com/bedrock/) as the reasoning engine and [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) for tool integration. It can be deployed locally, as an MCP server for any AI assistant, or to [Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/) for production use.

---

## Architecture

### All 3 Deployment Modes

```
 Mode 1: CLI Agent (local)
 ─────────────────────────
 Terminal ──▶ Strands Agent ──▶ MCP Server ──▶ Skills ──▶ AWS APIs
              (Bedrock Claude)   (subprocess)


 Mode 2: MCP Server (for AI assistants)
 ───────────────────────────────────────
 Kiro / Claude Desktop / Q Developer
       │
       │ MCP protocol (stdio)
       ▼
 MCP Server (FastMCP) ──▶ Skills ──▶ AWS APIs
 (16 tools exposed)


 Mode 3: AgentCore (production)
 ──────────────────────────────
 Your App / API / Slack Bot
       │
       │ invoke_agent_runtime() API
       ▼
 ┌─────────────────────────────────────────────────┐
 │          Amazon Bedrock AgentCore                │
 │  ┌───────────────────────────────────────────┐  │
 │  │  AgentCore Gateway (managed by AWS)       │  │
 │  │  • Auth & IAM integration                 │  │
 │  │  • Request routing                        │  │
 │  │  • Auto-scaling                           │  │
 │  │  • Observability (CloudWatch traces)      │  │
 │  └─────────────────┬─────────────────────────┘  │
 │                    │                             │
 │  ┌─────────────────▼─────────────────────────┐  │
 │  │  AgentCore Runtime (your container)       │  │
 │  │  ┌─────────────────────────────────────┐  │  │
 │  │  │  Strands Agent (Bedrock Claude)     │  │  │
 │  │  │       │                             │  │  │
 │  │  │       ▼                             │  │  │
 │  │  │  MCP Server (subprocess)            │  │  │
 │  │  │  └── 12 Skills + Remediation        │  │  │
 │  │  └─────────────────────────────────────┘  │  │
 │  └───────────────────────────────────────────┘  │
 └─────────────────────┬───────────────────────────┘
                       │ boto3
                       ▼
                 Your AWS Account
                 (EC2, RDS, S3, Lambda, etc.)
```

### Deployment Modes

| Mode | How It Works | Best For |
|------|-------------|----------|
| **CLI Agent** | Interactive terminal chat | Personal use, testing |
| **MCP Server** | Expose tools to any MCP client | Kiro, Claude Desktop, Q Developer |
| **AgentCore** | Managed serverless runtime | Production, team use, API access |

---

## Tech Stack

| Component | Technology | Link |
|-----------|-----------|------|
| Agent Framework | Strands Agents SDK | [strandsagents.com](https://strandsagents.com/) |
| AI Model | Amazon Bedrock (Claude) | [aws.amazon.com/bedrock](https://aws.amazon.com/bedrock/) |
| Tool Protocol | Model Context Protocol (MCP) | [modelcontextprotocol.io](https://modelcontextprotocol.io/) |
| MCP Server | FastMCP | [gofastmcp.com](https://gofastmcp.com/) |
| AWS SDK | Boto3 | [boto3.amazonaws.com](https://boto3.amazonaws.com/v1/documentation/api/latest/) |
| Production Runtime | Amazon Bedrock AgentCore | [docs.aws.amazon.com/bedrock-agentcore](https://docs.aws.amazon.com/bedrock-agentcore/) |
| Language | Python 3.10+ | |
| CLI | Click + Rich | |

---

## 12 Scanning Skills

| Skill | Icon | What It Does |
|-------|------|-------------|
| cost-anomaly | 💰 | Detects spending spikes, week-over-week changes, new services |
| zombie-hunter | 🧟 | Finds idle EC2/RDS, unattached EBS, unused EIPs and NAT Gateways |
| security-posture | 🛡️ | Checks GuardDuty, Security Hub, open security groups, public S3, old IAM keys |
| capacity-planner | 📊 | Monitors EC2 quotas, ODCR utilization, SageMaker capacity |
| event-analysis | 🔍 | Analyzes CloudTrail for high-risk events, root usage, unauthorized calls |
| resiliency-gaps | 🏗️ | Checks all 6 Well-Architected pillars (reliability, security, performance, ops, sustainability) |
| tag-enforcer | 🏷️ | Finds EC2, RDS, S3, Lambda missing mandatory tags (Environment, Team, Owner) |
| lifecycle-tracker | ⏳ | Flags deprecated Lambda runtimes, EOL RDS engines, old Fargate platforms |
| health-monitor | 🏥 | Pulls AWS Health events, Trusted Advisor checks |
| quota-guardian | 📏 | Monitors 12 key service quotas approaching limits |
| arch-diagram | 🏗️ | Discovers all resources and generates architecture diagrams via Bedrock |
| costopt-intelligence | 🎯 | Savings Plan/RI recommendations, right-sizing, GP2→GP3, S3 tiering, NAT data costs |

### Plus 4 Utility Tools

| Tool | What It Does |
|------|-------------|
| scan_all_skills | Runs all 12 skills at once |
| remediate_finding | Fixes issues — 18 auto-fix actions (delete volumes, restrict SGs, apply tags, etc.) |
| list_skills | Lists available skills |
| get_account_info | Gets account ID and regions |

---

## Prerequisites

1. **Python 3.10+** — Check with `python3 --version`
2. **AWS credentials** — Configured via `aws configure` or environment variables
3. **Amazon Bedrock access** — Enable Claude Haiku 4.5 model in the [Bedrock console](https://console.aws.amazon.com/bedrock/) (us-east-1)
4. **IAM permissions** — `ReadOnlyAccess` for scanning, plus specific write permissions for remediation

---

## Installation Guide

### Step 1: Clone the Repository

```bash
git clone https://github.com/YOUR_ORG/aws-ops-agent.git
cd aws-ops-agent
```

### Step 2: Create a Virtual Environment (Python 3.10+)

```bash
# Using uv (recommended)
uv venv .venv --python 3.10
source .venv/bin/activate

# Or using standard venv
python3.10 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies

```bash
# Core + MCP + Agent
pip install -e ".[agent]"

# Or minimal (MCP server only, no Strands agent)
pip install -e ".[mcp]"
```

### Step 4: Configure AWS Credentials

```bash
# Option A: Named profile
aws configure --profile your-profile

# Option B: Environment variables
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_REGION=us-east-1

# Option C: SSO
aws sso login --profile your-profile
```

### Step 5: Verify Bedrock Access

```bash
aws bedrock list-foundation-models --region us-east-1 --query 'modelSummaries[?contains(modelId,`claude`)].modelId' --output table
```

---

## Usage

### Mode 1: Interactive CLI Agent

Chat naturally with the agent in your terminal:

```bash
python -m ops_agent.cli --profile your-profile agent
```

Example conversation:
```
🔮  ❯❯  What skills do you have?

I have 12 scanning skills covering cost, security, compliance...

🔮  ❯❯  Scan my account for zombie resources

Running zombie-hunter... Found 7 findings:
- Idle EC2: i-0abc123 (t3.large, CPU 0.5%) — $73/mo
- Unattached EBS: vol-xyz (100GB gp2) — $8/mo
...

🔮  ❯❯  Fix the idle EC2 i-0abc123

I'll stop instance i-0abc123. This will halt the instance but preserve
the EBS volumes. Monthly savings: ~$73. Proceed?

🔮  ❯❯  yes

Done. Instance i-0abc123 stopped.
```

Slash commands:
- `/skills` — List all 12 skills
- `/tools` — List all 16 MCP tools
- `/model` — Show or switch model (`/model sonnet`, `/model opus`)
- `/help` — Show help
- `/quit` — Exit

Choose your model:
```bash
# Default (Haiku — fast, cheap)
python -m ops_agent.cli --profile your-profile agent

# Sonnet (smarter, more expensive)
python -m ops_agent.cli --profile your-profile agent --model sonnet

# Opus (most capable)
python -m ops_agent.cli --profile your-profile agent --model opus
```

### Mode 2: MCP Server

Expose the 16 tools to any MCP-compatible client:

```bash
# Start MCP server (stdio — for Kiro, Claude Desktop, Q Developer)
python -m ops_agent.cli --profile your-profile mcp

# Start MCP server (SSE — for remote clients)
python -m ops_agent.cli --profile your-profile mcp --transport sse --port 8081
```

#### Connect from Kiro

Add to `.kiro/settings/mcp.json`:
```json
{
  "mcpServers": {
    "aws-ops-agent": {
      "command": "python3.10",
      "args": ["-m", "ops_agent.mcp_server"],
      "env": { "AWS_PROFILE": "your-profile" }
    }
  }
}
```

#### Connect from Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "aws-ops-agent": {
      "command": "python3.10",
      "args": ["-m", "ops_agent.mcp_server"],
      "env": { "AWS_PROFILE": "your-profile" }
    }
  }
}
```

#### Connect from Amazon Q Developer CLI

Add to `~/.aws/amazonq/mcp.json`:
```json
{
  "mcpServers": {
    "aws-ops-agent": {
      "command": "python3.10",
      "args": ["-m", "ops_agent.mcp_server"],
      "env": { "AWS_PROFILE": "your-profile" }
    }
  }
}
```

### Mode 3: Deploy to Amazon Bedrock AgentCore

For production deployment as a managed service:

```bash
# Install AgentCore toolkit
pip install bedrock-agentcore-starter-toolkit

# Configure and deploy
cd deploy/agentcore
agentcore configure --entrypoint agent.py
agentcore launch

# Test
agentcore invoke '{"prompt": "Scan my account for security issues"}'

# Invoke programmatically
python -c "
import boto3, json
client = boto3.client('bedrock-agentcore', region_name='us-east-1')
response = client.invoke_agent_runtime(
    agentRuntimeArn='YOUR_AGENT_ARN',
    runtimeSessionId='session-' + 'x' * 30,
    payload=json.dumps({'prompt': 'Run all skills'})
)
print(json.loads(response['response'].read()))
"

# Tear down
agentcore destroy
```

See [Amazon Bedrock AgentCore docs](https://docs.aws.amazon.com/bedrock-agentcore/) for full details.

---

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `AWS_PROFILE` | default | AWS CLI profile |
| `AWS_REGION` | us-east-1 | AWS region |
| `OPS_AGENT_BEDROCK_MODEL` | claude-haiku-4.5 | Bedrock model ID |
| `OPS_AGENT_BEDROCK_REGION` | us-east-1 | Bedrock region |

Model shortcuts for CLI `--model` flag:
- `haiku` → Claude Haiku 4.5 (fast, cheap)
- `sonnet` → Claude Sonnet 4 (balanced)
- `opus` → Claude Opus 4 (most capable)

---

## AWS Permissions

### For Scanning (read-only)

`ReadOnlyAccess` managed policy covers most skills. Key permissions:
```
ec2:Describe*, rds:Describe*, s3:List*, lambda:List*,
cloudwatch:GetMetricStatistics, cloudtrail:LookupEvents,
guardduty:GetFindings, securityhub:GetFindings,
ce:GetCostAndUsage, ce:GetSavingsPlansPurchaseRecommendation,
service-quotas:GetServiceQuota, bedrock:InvokeModel
```

### For Remediation (write)

```
ec2:DeleteVolume, ec2:StopInstances, ec2:RevokeSecurityGroupIngress,
rds:ModifyDBInstance, s3:PutPublicAccessBlock, iam:UpdateAccessKey,
lambda:UpdateFunctionConfiguration
```

---

## Project Structure

```
aws-ops-agent/
├── ops_agent/
│   ├── mcp_server.py          # MCP server — 16 tools via FastMCP
│   ├── strands_agent.py       # Strands agent — interactive CLI
│   ├── cli.py                 # Click CLI commands
│   ├── core.py                # Finding, SkillResult, SkillRegistry
│   ├── aws_client.py          # Boto3 helpers
│   └── skills/                # 12 scanning skills
│       ├── cost_anomaly.py
│       ├── zombie_hunter.py
│       ├── security_posture.py
│       ├── capacity_planner.py
│       ├── event_analysis.py
│       ├── resiliency_gaps.py
│       ├── tag_enforcer.py
│       ├── lifecycle_tracker.py
│       ├── health_monitor.py
│       ├── quota_guardian.py
│       ├── arch_diagram.py
│       └── costopt_intelligence.py
├── deploy/
│   └── agentcore/             # AgentCore deployment
│       ├── agent.py
│       ├── requirements.txt
│       └── deploy.sh
├── tests/                     # 359 unit tests
├── setup.py
└── README.md
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `command not found: ops-agent` | Use `python -m ops_agent.cli` instead |
| `InvalidClientTokenId` | AWS credentials expired — run `aws sso login` or `aws configure` |
| Bedrock `AccessDenied` | Enable Claude model in [Bedrock console](https://console.aws.amazon.com/bedrock/) |
| FastMCP banner showing | Update to latest version — banner suppression is built in |
| MCP cleanup error on quit | Cosmetic only — agent worked fine, safe to ignore |
| Skills return no findings | Check IAM permissions — need `ReadOnlyAccess` minimum |

---

## Links

- [Strands Agents SDK](https://strandsagents.com/)
- [Amazon Bedrock](https://aws.amazon.com/bedrock/)
- [Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [FastMCP](https://gofastmcp.com/)
- [Deploy Strands to AgentCore](https://strandsagents.com/latest/documentation/docs/user-guide/deploy/deploy_to_bedrock_agentcore/python/)
