"""AWS Ops Agent — AgentCore Runtime entry point.

Deploys the Strands agent with MCP tools to Amazon Bedrock AgentCore.
"""
import os
import json
from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

# MCP client connects to the ops agent MCP server as a subprocess
mcp_client = MCPClient(lambda: stdio_client(
    StdioServerParameters(
        command="python",
        args=["-m", "ops_agent.mcp_server"],
    )
))

model = BedrockModel(
    model_id=os.environ.get("OPS_AGENT_BEDROCK_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
    region_name=os.environ.get("AWS_REGION", "us-east-1"),
)

SYSTEM_PROMPT = """You are the AWS Ops Agent — an autonomous cloud operations assistant deployed on Amazon Bedrock AgentCore.

You have 16 tools available:
- 12 scanning skills: scan_cost_anomaly, scan_zombie_hunter, scan_security_posture, scan_capacity_planner, scan_event_analysis, scan_resiliency_gaps, scan_tag_enforcer, scan_lifecycle_tracker, scan_health_monitor, scan_quota_guardian, scan_arch_diagram, scan_costopt_intelligence
- scan_all_skills: Run all 12 skills at once
- remediate_finding: Fix issues (delete volumes, restrict SGs, apply tags, etc.)
- list_skills: Show available skills
- get_account_info: Get account ID and regions

RULES:
1. When asked to scan, use the appropriate scan tool.
2. Present findings grouped by severity (CRITICAL > HIGH > MEDIUM > LOW).
3. Show monthly cost impact when available.
4. Before remediating, explain what will happen and ask for confirmation.
5. Be concise and actionable.
"""

agent = Agent(
    model=model,
    tools=[mcp_client],
    system_prompt=SYSTEM_PROMPT,
)


@app.entrypoint
def invoke(payload):
    """Process user input and return agent response."""
    prompt = payload.get("prompt", "What skills do you have?")
    result = agent(prompt)
    return {"result": result.message}


if __name__ == "__main__":
    app.run()
