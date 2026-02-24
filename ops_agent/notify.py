"""Notification handlers — Slack, SNS, console."""
import json
import requests
from ops_agent.core import Finding, Severity, SkillResult


def notify_console(result: SkillResult):
    """Print findings to console (always active)."""
    pass  # Handled by CLI renderer


def notify_slack(webhook_url: str, result: SkillResult):
    """Send findings summary to Slack."""
    if not result.findings:
        return

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"🤖 Ops Agent — {result.skill_name}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": (
            f"*Findings:* {len(result.findings)} | "
            f"*Critical:* {result.critical_count} | "
            f"*Monthly Impact:* ${result.total_impact:,.0f}"
        )}},
        {"type": "divider"},
    ]

    for f in result.findings[:10]:
        emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}.get(f.severity.value, "⚪")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": (
                f"{emoji} *{f.title}*\n"
                f"Account: `{f.account_id}` | Region: `{f.region}`\n"
                f"{f.description}\n"
                f"💰 Impact: ${f.monthly_impact:,.0f}/mo | Action: _{f.recommended_action}_"
            )}
        })

    if len(result.findings) > 10:
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
                       "text": f"_... and {len(result.findings) - 10} more findings_"}})

    try:
        requests.post(webhook_url, json={"blocks": blocks}, timeout=10)
    except Exception:
        pass


def notify_sns(topic_arn: str, result: SkillResult, profile=None):
    """Publish findings to SNS topic."""
    if not result.findings:
        return
    import boto3
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    sns = session.client("sns", region_name=topic_arn.split(":")[3])
    message = {
        "skill": result.skill_name,
        "findings_count": len(result.findings),
        "critical_count": result.critical_count,
        "monthly_impact": result.total_impact,
        "findings": [f.to_dict() for f in result.findings[:20]],
    }
    try:
        sns.publish(TopicArn=topic_arn, Message=json.dumps(message, indent=2),
                    Subject=f"Ops Agent: {len(result.findings)} findings from {result.skill_name}")
    except Exception:
        pass
