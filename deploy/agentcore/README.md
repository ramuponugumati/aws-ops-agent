# Deploy AWS Ops Agent to Bedrock AgentCore

Deploy the AWS Ops Agent as a managed Bedrock AgentCore runtime. No Lambda, no infrastructure to manage — AgentCore handles scaling, auth, and invocation.

## Prerequisites

- Python 3.10+
- AWS credentials with Bedrock and AgentCore permissions
- `bedrock-agentcore-starter-toolkit` installed

```bash
pip install bedrock-agentcore-starter-toolkit
```

## Quick Deploy

```bash
cd deploy/agentcore

# Configure and deploy (one command)
./deploy.sh

# Or step by step:
agentcore configure --entrypoint agent.py
agentcore launch
```

## Test

```bash
# List skills
agentcore invoke '{"prompt": "What skills do you have?"}'

# Scan for zombie resources
agentcore invoke '{"prompt": "Scan my account for idle EC2 and unattached EBS volumes"}'

# Full assessment
agentcore invoke '{"prompt": "Run all skills and give me a prioritized summary"}'

# Security check
agentcore invoke '{"prompt": "Check my security posture in us-east-1"}'

# Cost optimization
agentcore invoke '{"prompt": "What Savings Plan recommendations do you have?"}'
```

## Test Locally First

```bash
# Requires Docker/Finch/Podman
./deploy.sh --local

# Then test
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What skills do you have?"}'
```

## Invoke Programmatically

```python
import boto3
import json

client = boto3.client('bedrock-agentcore', region_name='us-east-1')

response = client.invoke_agent_runtime(
    agentRuntimeArn='arn:aws:bedrock-agentcore:us-east-1:YOUR_ACCOUNT:runtime/YOUR_AGENT_ID',
    runtimeSessionId='session-' + 'x' * 30,
    payload=json.dumps({"prompt": "Scan for security issues"})
)

result = json.loads(response['response'].read())
print(result)
```

## Tear Down

```bash
./deploy.sh --destroy
```

## Architecture

```
User/App → AgentCore Gateway → Strands Agent (container)
                                    ├── Bedrock Claude (reasoning)
                                    └── MCP Server (in-process)
                                         └── 12 Skills + Remediation
```

AgentCore manages the container lifecycle, scaling, and gateway. The Strands agent uses Bedrock Claude for reasoning and the MCP server (running as a subprocess) for tool execution.
