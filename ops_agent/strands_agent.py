"""Strands Agent — conversational AWS ops agent using MCP tools."""
import os
import sys
import threading
import time

from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters


SYSTEM_PROMPT = """You are the AWS Ops Agent — an autonomous cloud operations assistant.

You have access to 12 scanning skills that analyze AWS environments:
- scan_cost_anomaly: Detect spending spikes and new services
- scan_zombie_hunter: Find idle EC2/RDS, unattached EBS, unused EIPs/NATs
- scan_security_posture: GuardDuty, Security Hub, open SGs, public S3, old IAM keys
- scan_capacity_planner: EC2 quotas, ODCR utilization, SageMaker capacity
- scan_event_analysis: CloudTrail high-risk events, root usage, Config compliance
- scan_resiliency_gaps: All 6 Well-Architected pillars
- scan_tag_enforcer: Find untagged EC2, RDS, S3, Lambda
- scan_lifecycle_tracker: Deprecated runtimes, EOL engines
- scan_health_monitor: AWS Health events, Trusted Advisor
- scan_quota_guardian: Service quotas approaching limits
- scan_arch_diagram: Resource discovery + architecture diagrams
- scan_costopt_intelligence: Savings Plans, RI, right-sizing, EBS/S3 optimization
- scan_all_skills: Run all 12 skills at once

You also have:
- remediate_finding: Fix issues (delete volumes, restrict SGs, apply tags, etc.)
- list_skills: Show available skills
- get_account_info: Get account ID and regions

RULES:
1. When asked to scan, use the appropriate scan tool. For a full assessment, use scan_all_skills.
2. Present findings grouped by severity (CRITICAL > HIGH > MEDIUM > LOW).
3. Always show the monthly cost impact when available.
4. Before remediating, explain what will happen and ask for confirmation.
5. For remediation, pass the exact skill, title, resource_id, and region from the scan results.
6. Be concise and actionable. Prioritize critical and high severity findings.
"""


AVAILABLE_MODELS = {
    "haiku": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "sonnet": "us.anthropic.claude-sonnet-4-20250514-v1:0",
    "opus": "us.anthropic.claude-opus-4-20250514-v1:0",
}
DEFAULT_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def create_agent(profile: str = None, region: str = "us-east-1", model_id: str = None):
    """Create a Strands agent connected to the Ops Agent MCP server."""

    # MCP client connects to the ops agent MCP server as a subprocess
    # Redirect stderr to suppress FastMCP banner
    server_command = sys.executable
    server_args = ["-m", "ops_agent.mcp_server"]

    env = dict(os.environ)
    if profile:
        env["AWS_PROFILE"] = profile
    env["FASTMCP_LOG_LEVEL"] = "CRITICAL"
    env["PYTHONWARNINGS"] = "ignore"

    mcp_client = MCPClient(lambda: stdio_client(
        StdioServerParameters(
            command=server_command,
            args=server_args,
            env=env,
        )
    ))

    effective_model = model_id or os.environ.get("OPS_AGENT_BEDROCK_MODEL", DEFAULT_MODEL)

    # Create a boto3 session with the correct profile for Bedrock
    import boto3
    session_kwargs = {}
    if profile:
        session_kwargs["profile_name"] = profile
    bedrock_region = os.environ.get("OPS_AGENT_BEDROCK_REGION", region)
    session_kwargs["region_name"] = bedrock_region
    bedrock_session = boto3.Session(**session_kwargs)

    model = BedrockModel(
        model_id=effective_model,
        boto_session=bedrock_session,
    )

    agent = Agent(
        model=model,
        tools=[mcp_client],
        system_prompt=SYSTEM_PROMPT,
    )

    return agent


def run_interactive(profile: str = None, region: str = "us-east-1", model_id: str = None):
    """Run the agent in interactive chat mode."""
    effective_model = model_id or os.environ.get("OPS_AGENT_BEDROCK_MODEL", DEFAULT_MODEL)
    agent = create_agent(profile=profile, region=region, model_id=effective_model)

    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    PURPLE = "\033[38;2;138;79;255m"  # Kiro purple
    RESET = "\033[0m"

    # Get terminal width for centering
    try:
        cols = os.get_terminal_size().columns
    except Exception:
        cols = 80

    def center(text, raw_len=None):
        """Center text accounting for ANSI codes."""
        if raw_len is None:
            import re
            raw_len = len(re.sub(r'\033\[[^m]*m', '', text))
        pad = max(0, (cols - raw_len) // 2)
        return " " * pad + text

    # Clear screen
    print("\033[2J\033[H", end="")

    # Robot banner with tools below
    PURPLE = "\033[38;2;138;79;255m"
    ORANGE = "\033[38;2;255;165;0m"

    robot = [
        "     _____     ",
        "    |     |    ",
        "    | O O |    ",
        "    |  _  |    ",
        "    |_____|    ",
        "   /|     |\\   ",
        "  / |     | \\  ",
        "    |     |    ",
        "   / \\   / \\   ",
    ]

    print()
    for line in robot:
        print(center(f"{BOLD}{PURPLE}{line}{RESET}", len(line)))
    print()
    print(center(f"{BOLD}{ORANGE}AWS  OPS  AGENT{RESET}", 15))
    print(center(f"{DIM}Autonomous Cloud Operations{RESET}", 27))
    print()
    print(center(f"💰 🧟 🛡️ 📊 🔍 🏗️  🏷️ ⏳ 🏥 📏 🏗️ 🎯", 36))
    print()

    info = f"Profile: {profile or 'default'} | Region: {region} | Model: {effective_model.split('.')[-1][:30]}"
    BRIGHT_YELLOW = "\033[93;1m"
    print(center(f"{BRIGHT_YELLOW}{info}{RESET}", len(info)))
    print()
    print(f"{YELLOW}Commands:{RESET}")
    print(f"  /quit       Exit the agent")
    print(f"  /skills     List all 12 scanning skills")
    print(f"  /tools      List all MCP tools")
    print(f"  /model      Show current model or switch (e.g., /model sonnet)")
    print(f"  /help       Show this help")
    print()
    print(f"{GREEN}Try asking:{RESET}")
    print(f"  • What skills do you have?")
    print(f"  • Scan my account for zombie resources")
    print(f"  • Check my security posture in us-east-1")
    print(f"  • What are my cost optimization opportunities?")
    print(f"  • Run all skills and give me a summary")
    print(f"  • Are there any deprecated Lambda runtimes?")
    print(f"  • Show me untagged resources")
    print(f"  • What Savings Plan should I buy?")
    print()

    while True:
        try:
            CYAN = "\033[96m"
            BOLD = "\033[1m"
            PURPLE = "\033[38;2;138;79;255m"
            RESET = "\033[0m"
            user_input = input(f"{BOLD}{PURPLE}  🔮  ❯❯  {RESET}").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q", "/quit", "/exit", "/q"):
                print("Goodbye!")
                break

            # Slash commands
            if user_input == "/help":
                print(f"\n{YELLOW}Commands:{RESET}")
                print(f"  /quit       Exit the agent")
                print(f"  /skills     List all 12 scanning skills")
                print(f"  /tools      List all MCP tools")
                print(f"  /model      Show current model or switch (e.g., /model sonnet)")
                print(f"  /help       Show this help\n")
                continue

            if user_input == "/skills":
                print(f"\n{BOLD}{CYAN}12 Scanning Skills:{RESET}")
                print(f"  💰 cost-anomaly         Spending spikes, week-over-week changes")
                print(f"  🧟 zombie-hunter        Idle EC2/RDS, unattached EBS, unused EIPs")
                print(f"  🛡️  security-posture     GuardDuty, Security Hub, open SGs, public S3")
                print(f"  📊 capacity-planner     EC2 quotas, ODCR utilization, SageMaker")
                print(f"  🔍 event-analysis       CloudTrail high-risk events, root usage")
                print(f"  🏗️  resiliency-gaps      All 6 Well-Architected pillars")
                print(f"  🏷️  tag-enforcer         Untagged EC2, RDS, S3, Lambda")
                print(f"  ⏳ lifecycle-tracker     Deprecated runtimes, EOL engines")
                print(f"  🏥 health-monitor       AWS Health events, Trusted Advisor")
                print(f"  📏 quota-guardian        Service quotas approaching limits")
                print(f"  🏗️  arch-diagram          Resource discovery + architecture maps")
                print(f"  🎯 costopt-intelligence  Savings Plans, RI, right-sizing, EBS/S3 opt\n")
                continue

            if user_input == "/tools":
                print(f"\n{BOLD}{CYAN}16 MCP Tools:{RESET}")
                print(f"  {GREEN}Scanning:{RESET}")
                print(f"    scan_cost_anomaly       scan_zombie_hunter")
                print(f"    scan_security_posture   scan_capacity_planner")
                print(f"    scan_event_analysis     scan_resiliency_gaps")
                print(f"    scan_tag_enforcer       scan_lifecycle_tracker")
                print(f"    scan_health_monitor     scan_quota_guardian")
                print(f"    scan_arch_diagram       scan_costopt_intelligence")
                print(f"    scan_all_skills")
                print(f"  {GREEN}Actions:{RESET}")
                print(f"    remediate_finding       Fix issues (18 auto-fix actions)")
                print(f"  {GREEN}Info:{RESET}")
                print(f"    list_skills             get_account_info\n")
                continue

            if user_input.startswith("/model"):
                parts = user_input.split(maxsplit=1)
                if len(parts) == 1:
                    print(f"\n{CYAN}Current model:{RESET} {effective_model}")
                    print(f"{DIM}Available shortcuts: haiku, sonnet, opus{RESET}")
                    print(f"{DIM}Or pass a full model ID: /model us.anthropic.claude-sonnet-4-20250514-v1:0{RESET}\n")
                else:
                    new_model = parts[1].strip()
                    new_model = AVAILABLE_MODELS.get(new_model, new_model)
                    effective_model = new_model
                    print(f"\n{GREEN}Switching model to:{RESET} {effective_model}")
                    print(f"{DIM}Restarting agent...{RESET}")
                    agent = create_agent(profile=profile, region=region, model_id=effective_model)
                    print(f"{GREEN}Ready.{RESET}\n")
                continue
            response = agent(user_input)
            print(f"\n{response}\n")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}\n")

    # Suppress MCP cleanup errors on exit
    import warnings
    warnings.filterwarnings("ignore")
    try:
        del agent
    except Exception:
        pass
    os._exit(0)
