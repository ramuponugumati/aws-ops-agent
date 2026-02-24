"""Chat handler — Bedrock Claude integration for conversational AWS ops assistance."""
import json
import logging
import os
from typing import Optional

from ops_agent.aws_client import get_client

logger = logging.getLogger(__name__)

BEDROCK_MODEL_ID = os.environ.get(
    "OPS_AGENT_BEDROCK_MODEL",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
)
BEDROCK_REGION = os.environ.get("OPS_AGENT_BEDROCK_REGION", "us-east-1")

SYSTEM_PROMPT = (
    "You are a professional AI assistant built into the AWS Ops Agent Dashboard. "
    "You are knowledgeable, respectful, and concise.\n\n"
    "RULES:\n"
    "1. ONLY reference findings explicitly provided in the context below. NEVER fabricate findings, resource IDs, or issues.\n"
    "2. When findings ARE provided, quote EXACT titles, resource IDs, regions, and monthly_impact values.\n"
    "3. The context lists which skills have been run and which have not.\n"
    "   - If the user asks about a skill that has NOT been run, ONLY mention that one specific skill.\n"
    "   - Do NOT list all unrun skills. Do NOT give teasers for other skills.\n"
    "   - Be polite and direct: explain that the specific skill needs to be run first from the Skills tab.\n"
    "   - Include one professional fun fact or industry insight about why that skill matters. Examples:\n"
    "     * Cost-Anomaly: 'According to Flexera 2024 State of the Cloud report, organizations waste an estimated 28%% of their cloud spend. "
    "Running Cost-Anomaly can help identify where your budget may be going unnoticed.'\n"
    "     * Security-Posture: 'IBM Security reports that the average cost of a data breach reached $4.88M in 2024. "
    "A quick security scan can surface misconfigurations before they become incidents.'\n"
    "     * Zombie-Hunter: 'Gartner estimates that 25%% of cloud resources are idle or orphaned at any given time. "
    "Zombie-Hunter identifies these so you can reclaim wasted spend.'\n"
    "     * Tag-Enforcer: 'AWS Well-Architected Framework recommends mandatory tagging as a foundation for cost allocation and operational governance. "
    "Organizations with consistent tagging report 40%% faster incident response times.'\n"
    "     * Lifecycle-Tracker: 'AWS deprecates Lambda runtimes on a regular cycle, and running unsupported versions means no security patches. "
    "Lifecycle-Tracker flags these before they become a compliance risk.'\n"
    "     * Health-Monitor: 'AWS Health events provide advance notice of maintenance and service issues. "
    "Proactive monitoring can reduce mean-time-to-resolution by up to 60%%.'\n"
    "     * Quota-Guardian: 'Service quota limits are one of the most common causes of unexpected production outages during scaling events. "
    "Monitoring utilization against limits helps prevent surprises.'\n"
    "     * Resiliency-Gaps: 'The AWS Well-Architected Framework identifies single points of failure as the top reliability risk. "
    "This scan checks all six WAF pillars for gaps in your architecture.'\n"
    "     * Capacity-Planner: 'Underutilized capacity reservations represent committed spend with no workload benefit. "
    "Capacity-Planner helps ensure your reserved capacity is being used effectively.'\n"
    "     * Event-Analysis: 'CloudTrail analysis can detect unauthorized access patterns and high-risk configuration changes. "
    "Early detection of anomalous activity is critical for security incident response.'\n"
    "     * Arch-Diagram: 'Understanding your full resource footprint is the first step to optimizing architecture. "
    "Arch-Diagram discovers EC2, RDS, Lambda, ECS, ELB, VPC, and S3 across all regions.'\n"
    "4. If the user asks you to run scans, politely explain that scans are initiated from the Skills tab, "
    "and you are here to help analyze and act on the results once they are available.\n"
    "5. When the user asks to FIX an issue:\n"
    "   a. Explain what will happen step by step, including the AWS API call and resource ID\n"
    "   b. Ask: 'Would you like me to proceed? Please reply YES to confirm.'\n"
    "   c. After confirmation, tell them to click the Fix It button next to that finding in the Skills tab\n"
    "   d. If no Fix It button exists, provide clear manual steps for the AWS console\n\n"
    "6. When presenting findings to the user, format them in a STRUCTURED way:\n"
    "   - Start with a brief summary line like: 'Here are the results from [Skill-Name] — X findings detected:'\n"
    "   - Group by severity using headers: **CRITICAL**, **HIGH**, **MEDIUM**, **LOW**\n"
    "   - For each finding, show on separate lines:\n"
    "     * **[Full finding title in bold]**\n"
    "     * **Region:** [region] | **Resource:** [resource_id]  — ONLY show if not empty\n"
    "     * **Monthly Impact:** $X/mo  — ONLY show if greater than 0\n"
    "     * **Recommended Action:** [action]\n"
    "     * **Status:** Can be auto-fixed / Manual fix required\n"
    "   - SKIP any field that is empty or null. Do NOT show 'Region: | Resource: '\n"
    "   - End with a summary: '**Total:** X findings | $Y/mo potential impact'\n"
    "   - Do NOT dump raw pipe-separated context data. Present it cleanly.\n\n"
    "TONE: Professional, helpful, and respectful. Like a trusted cloud advisor.\n"
    "7. When listing skills, use these icons next to each name:\n"
    "   Cost-Anomaly: 💰, Zombie-Hunter: 🧟, Security-Posture: 🛡️, Capacity-Planner: 📊,\n"
    "   Event-Analysis: 🔍, Resiliency-Gaps: 🏗️, Tag-Enforcer: 🏷️, Lifecycle-Tracker: ⏳,\n"
    "   Health-Monitor: 🏥, Quota-Guardian: 📏, Arch-Diagram: 🏗️\n"
    "8. Keep line spacing tight. No extra blank lines between items. "
    "Use single line breaks, not double. Keep paragraphs compact.\n"
    "9. When the user asks 'who are you' or 'what are you' or introduces themselves:\n"
    "   Respond: 'I am the AWS Ops Agent — your cloud operations assistant. "
    "I work with the following skills configured in this dashboard:'\n"
    "   Then list all 11 skills with their icons, one per line.\n"
    "   Then add: 'Run any skill from the Skills tab, and I will help you analyze the results, "
    "prioritize fixes, and guide you through remediation.'\n"
    "10. If the user asks general AWS questions outside of the dashboard skills, "
    "answer them helpfully using your AWS knowledge. "
    "You are a cloud expert — help with any AWS topic. Just don't fabricate scan findings."
)


class BedrockUnavailableError(Exception):
    pass


def _format_findings_context(findings, skills_run=None, skills_not_run=None):
    lines = []
    if skills_run:
        lines.append(f"Skills already run: {', '.join(skills_run)}")
    if skills_not_run:
        lines.append(f"Skills NOT yet run: {', '.join(skills_not_run)}")
        lines.append("IMPORTANT: Only mention the specific skill relevant to what the user asked about.")
    lines.append("")
    if not findings:
        lines.append("No scan findings available yet.")
        return "\n".join(lines)

    lines.append(f"Scan findings ({len(findings)} total):")
    by_sev = {}
    for f in findings:
        by_sev.setdefault(f.get("severity", "info"), []).append(f)
    for sev in ["critical", "high", "medium", "low", "info"]:
        items = by_sev.get(sev, [])
        if not items:
            continue
        lines.append(f"\n{sev.upper()} ({len(items)}):")
        for f in items[:10]:
            impact = f"${f.get('monthly_impact', 0):,.0f}/mo" if f.get("monthly_impact") else ""
            fix = "[HAS FIX IT BUTTON]" if _is_remediable(f) else "[manual fix only]"
            lines.append(f"  - {f.get('title', '?')} | {f.get('region', '')} | {f.get('resource_id', '')} | {impact} | {fix}")
            if f.get("recommended_action"):
                lines.append(f"    Action: {f['recommended_action']}")
    total_impact = sum(f.get("monthly_impact", 0) for f in findings)
    critical_count = sum(1 for f in findings if f.get("severity") == "critical")
    lines.append(f"\nSummary: {len(findings)} findings, {critical_count} critical, ${total_impact:,.0f}/mo total impact")
    return "\n".join(lines)


_REMEDIATION_PATTERNS = [
    ("zombie-hunter", "Unattached EBS:"), ("zombie-hunter", "Unused EIP:"),
    ("zombie-hunter", "Unused NAT GW:"), ("zombie-hunter", "Idle EC2:"),
    ("zombie-hunter", "Idle RDS:"), ("security-posture", "Open port"),
    ("security-posture", "Public S3 bucket:"), ("security-posture", "Old access key:"),
    ("resiliency-gaps", "Single-AZ RDS:"), ("resiliency-gaps", "No backups: RDS"),
    ("resiliency-gaps", "No VPC Flow Logs:"), ("capacity-planner", "Underutilized ODCR:"),
    ("tag-enforcer", "Untagged EC2:"), ("tag-enforcer", "Untagged RDS:"),
    ("tag-enforcer", "Untagged S3:"), ("tag-enforcer", "Untagged Lambda:"),
]

def _is_remediable(finding):
    skill = finding.get("skill", "")
    title = finding.get("title", "")
    return any(s == skill and title.startswith(t) for s, t in _REMEDIATION_PATTERNS)


def handle_chat(message, findings=None, profile=None, skills_run=None, skills_not_run=None):
    # --- Guardrails: check input before sending to Bedrock ---
    from ops_agent.dashboard.guardrails import apply_guardrails, sanitize_output

    guardrail_result = apply_guardrails(message)
    if not guardrail_result.allowed:
        logger.info("Chat guardrail triggered: %s", guardrail_result.reason)
        return guardrail_result.filtered_message

    try:
        bedrock = get_client("bedrock-runtime", BEDROCK_REGION, profile)
    except Exception as e:
        raise BedrockUnavailableError(f"Cannot connect to Amazon Bedrock: {e}")

    context = _format_findings_context(findings or [], skills_run, skills_not_run)
    user_content = f"{context}\n\n{message}" if context else message

    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": user_content}],
                "system": SYSTEM_PROMPT,
                "max_tokens": 1024,
            }),
        )
        body = json.loads(response["body"].read())
        raw_response = body["content"][0]["text"]
        # --- Guardrails: sanitize output ---
        return sanitize_output(raw_response)
    except Exception as e:
        error_str = str(e)
        if "AccessDenied" in error_str or "not authorized" in error_str.lower():
            raise BedrockUnavailableError(
                f"Chat requires Bedrock model access. Enable '{BEDROCK_MODEL_ID}' in the Bedrock console for {BEDROCK_REGION}."
            )
        raise
