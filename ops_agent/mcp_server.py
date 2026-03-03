"""MCP Server — exposes all Ops Agent skills and remediation as MCP tools."""
import json
import logging
import os
from typing import Optional

# Suppress FastMCP banner before importing
os.environ["FASTMCP_LOG_LEVEL"] = "ERROR"
logging.getLogger("fastmcp").setLevel(logging.ERROR)

from fastmcp import FastMCP

from ops_agent.core import SkillRegistry
from ops_agent.aws_client import get_regions, get_account_id
from ops_agent.dashboard.remediation import has_remediation, execute_remediation
import ops_agent.skills  # auto-register all skills

mcp = FastMCP(
    name="AWS Ops Agent",
    instructions=(
        "You are the AWS Ops Agent — an autonomous cloud operations assistant. "
        "Use the scan tools to analyze AWS environments for cost waste, security risks, "
        "resiliency gaps, and operational issues. Use the remediate tool to fix findings. "
        "Always scan before recommending fixes. Present findings grouped by severity."
    ),
)


def _serialize_result(result):
    """Convert a SkillResult to a JSON-serializable dict."""
    return {
        "skill_name": result.skill_name,
        "findings_count": len(result.findings),
        "critical_count": result.critical_count,
        "total_monthly_impact": round(result.total_impact, 2),
        "duration_seconds": round(result.duration_seconds, 1),
        "errors": result.errors,
        "findings": [f.to_dict() for f in result.findings],
    }


# --- Scan tools: one per skill ---

@mcp.tool()
def scan_cost_anomaly(region: Optional[str] = None, profile: Optional[str] = None) -> str:
    """Detect cost spikes, week-over-week spending changes, and unexpected new AWS services."""
    return _run_skill("cost-anomaly", region, profile)


@mcp.tool()
def scan_zombie_hunter(region: Optional[str] = None, profile: Optional[str] = None) -> str:
    """Find idle EC2 instances, unattached EBS volumes, unused Elastic IPs, and unused NAT Gateways."""
    return _run_skill("zombie-hunter", region, profile)


@mcp.tool()
def scan_security_posture(region: Optional[str] = None, profile: Optional[str] = None) -> str:
    """Check GuardDuty findings, Security Hub controls, open security groups, public S3 buckets, and old IAM access keys."""
    return _run_skill("security-posture", region, profile)


@mcp.tool()
def scan_capacity_planner(region: Optional[str] = None, profile: Optional[str] = None) -> str:
    """Check EC2 on-demand quotas, ODCR utilization, and SageMaker endpoint capacity."""
    return _run_skill("capacity-planner", region, profile)


@mcp.tool()
def scan_event_analysis(region: Optional[str] = None, profile: Optional[str] = None) -> str:
    """Analyze CloudTrail for high-risk events, root account usage, unauthorized API calls, and AWS Config compliance."""
    return _run_skill("event-analysis", region, profile)


@mcp.tool()
def scan_resiliency_gaps(region: Optional[str] = None, profile: Optional[str] = None) -> str:
    """Check all 6 Well-Architected pillars: reliability, security, performance, ops, cost, sustainability."""
    return _run_skill("resiliency-gaps", region, profile)


@mcp.tool()
def scan_tag_enforcer(region: Optional[str] = None, profile: Optional[str] = None) -> str:
    """Find EC2, RDS, S3, and Lambda resources missing mandatory tags (Environment, Team, Owner)."""
    return _run_skill("tag-enforcer", region, profile)


@mcp.tool()
def scan_lifecycle_tracker(region: Optional[str] = None, profile: Optional[str] = None) -> str:
    """Flag deprecated Lambda runtimes, end-of-life RDS engines, and outdated ECS Fargate platforms."""
    return _run_skill("lifecycle-tracker", region, profile)


@mcp.tool()
def scan_health_monitor(region: Optional[str] = None, profile: Optional[str] = None) -> str:
    """Check AWS Health events, service disruptions, scheduled maintenance, and Trusted Advisor checks."""
    return _run_skill("health-monitor", region, profile)


@mcp.tool()
def scan_quota_guardian(region: Optional[str] = None, profile: Optional[str] = None) -> str:
    """Monitor 12 key service quotas approaching limits across EC2, VPC, Lambda, RDS, S3, ECS, and more."""
    return _run_skill("quota-guardian", region, profile)


@mcp.tool()
def scan_arch_diagram(region: Optional[str] = None, profile: Optional[str] = None) -> str:
    """Discover all resources in the account and generate an architecture diagram."""
    return _run_skill("arch-diagram", region, profile)


@mcp.tool()
def scan_costopt_intelligence(region: Optional[str] = None, profile: Optional[str] = None) -> str:
    """Get Savings Plan and RI recommendations, right-sizing suggestions, EBS GP2-to-GP3 migration, S3 tiering, and NAT data cost analysis."""
    return _run_skill("costopt-intelligence", region, profile)


@mcp.tool()
def scan_all_skills(region: Optional[str] = None, profile: Optional[str] = None) -> str:
    """Run ALL 12 scanning skills in sequence and return a combined summary."""
    regions = get_regions(region, profile) if not region else [region]
    results = []
    for skill in SkillRegistry.all().values():
        try:
            result = skill.scan(regions, profile)
            results.append(_serialize_result(result))
        except Exception as e:
            results.append({"skill_name": skill.name, "error": str(e)})

    total_findings = sum(r.get("findings_count", 0) for r in results)
    total_critical = sum(r.get("critical_count", 0) for r in results)
    total_impact = sum(r.get("total_monthly_impact", 0) for r in results)

    summary = {
        "total_skills": len(results),
        "total_findings": total_findings,
        "total_critical": total_critical,
        "total_monthly_impact": round(total_impact, 2),
        "skills": results,
    }
    return json.dumps(summary, indent=2, default=str)


# --- Remediation tool ---

@mcp.tool()
def remediate_finding(
    skill: str,
    title: str,
    resource_id: str,
    region: str = "us-east-1",
    profile: Optional[str] = None,
    metadata: Optional[str] = None,
) -> str:
    """Execute a remediation action for a specific finding. Pass the skill name, finding title, resource_id, and region from a scan result.

    Args:
        skill: The skill that produced the finding (e.g., 'zombie-hunter')
        title: The exact finding title (e.g., 'Unattached EBS: vol-abc123')
        resource_id: The AWS resource ID to remediate
        region: AWS region of the resource
        profile: AWS CLI profile (optional)
        metadata: JSON string of additional metadata (optional)
    """
    finding = {
        "skill": skill,
        "title": title,
        "resource_id": resource_id,
        "region": region,
    }
    if metadata:
        try:
            finding["metadata"] = json.loads(metadata)
        except json.JSONDecodeError:
            pass

    if not has_remediation(finding):
        return json.dumps({"success": False, "message": f"No remediation available for: {title}"})

    result = execute_remediation(finding, profile)
    return json.dumps({
        "success": result.success,
        "action": result.action,
        "message": result.message,
        "resource_id": result.finding_id,
        "timestamp": result.timestamp,
    })


# --- Utility tools ---

@mcp.tool()
def list_skills() -> str:
    """List all available scanning skills with their descriptions."""
    skills = [
        {"name": s.name, "description": s.description, "version": s.version}
        for s in SkillRegistry.all().values()
    ]
    return json.dumps(skills, indent=2)


@mcp.tool()
def get_account_info(profile: Optional[str] = None) -> str:
    """Get the current AWS account ID and available regions."""
    acct = get_account_id(profile)
    regions = get_regions(profile=profile)
    return json.dumps({"account_id": acct, "regions": regions, "region_count": len(regions)})


# --- Helper ---

def _run_skill(skill_name: str, region: Optional[str], profile: Optional[str]) -> str:
    """Run a single skill and return JSON results."""
    skill = SkillRegistry.get(skill_name)
    if not skill:
        return json.dumps({"error": f"Unknown skill: {skill_name}"})
    regions = get_regions(region, profile) if not region else [region]
    result = skill.scan(regions, profile)
    return json.dumps(_serialize_result(result), indent=2, default=str)


# --- Entry point for stdio transport ---
if __name__ == "__main__":
    import sys
    import logging
    # Suppress ALL FastMCP output including the ASCII banner
    logging.getLogger("fastmcp").setLevel(logging.CRITICAL)
    logging.getLogger("fastmcp.server").setLevel(logging.CRITICAL)
    # Redirect stderr temporarily to suppress the banner
    import io
    _real_stderr = sys.stderr
    sys.stderr = io.StringIO()
    try:
        mcp.run(transport="stdio")
    finally:
        sys.stderr = _real_stderr
