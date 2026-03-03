import click
import json
import os
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich import box
from ops_agent.core import SkillRegistry, Severity
from collections import defaultdict
from ops_agent.aws_client import get_regions, get_account_id, get_client, build_org_tree
from ops_agent.notify import notify_slack, notify_sns
import ops_agent.skills  # triggers auto-registration

console = Console()

SEVERITY_COLORS = {"critical": "red", "high": "bright_red", "medium": "yellow", "low": "cyan", "info": "dim"}
SEVERITY_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}


@click.group()
@click.option("--region", default=None, help="AWS region (default: all)")
@click.option("--profile", default=None, help="AWS CLI profile")
@click.pass_context
def cli(ctx, region, profile):
    """🤖 AWS Operations Agent — Autonomous cloud operations"""
    ctx.ensure_object(dict)
    ctx.obj["region"] = region
    ctx.obj["profile"] = profile


@cli.command("run")
@click.option("--skill", default=None, help="Run specific skill (default: all)")
@click.option("--export", "export_file", default=None, help="Export to JSON")
@click.option("--slack-webhook", default=None, help="Slack webhook URL")
@click.option("--sns-topic", default=None, help="SNS topic ARN")
@click.pass_context
def run(ctx, skill, export_file, slack_webhook, sns_topic):
    """Run ops agent skills"""
    region = ctx.obj["region"]
    profile = ctx.obj["profile"]
    regions = get_regions(region, profile)
    acct = get_account_id(profile)

    skills_to_run = [SkillRegistry.get(skill)] if skill else list(SkillRegistry.all().values())
    skills_to_run = [s for s in skills_to_run if s]

    console.print(Panel(
        f"[bold cyan]🤖 AWS Operations Agent[/bold cyan]\n"
        f"[dim]Account: {acct} | Regions: {len(regions)} | Skills: {', '.join(s.name for s in skills_to_run)}[/dim]",
        box=box.DOUBLE, style="cyan"
    ))

    all_results = []
    for s in skills_to_run:
        console.print(f"\n[bold cyan]━━━ {s.name} ━━━[/bold cyan]")
        result = s.scan(regions, profile)
        all_results.append(result)
        _print_skill_result(result)

        if slack_webhook:
            notify_slack(slack_webhook, result)
        if sns_topic:
            notify_sns(sns_topic, result, profile)

    _print_summary(all_results)

    if export_file:
        _export(all_results, export_file, acct)


@cli.command("skills")
def list_skills():
    """List available skills"""
    table = Table(title="Available Skills", box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Version")
    for name, s in SkillRegistry.all().items():
        table.add_row(s.name, s.description, s.version)
    console.print(table)


@cli.command("org-scan")
@click.option("--skill", default=None, help="Run specific skill (default: all)")
@click.option("--role", default="OrganizationAccountAccessRole", help="Cross-account role name")
@click.option("--export", "export_file", default=None, help="Export to JSON")
@click.option("--slack-webhook", default=None, help="Slack webhook URL")
@click.pass_context
def org_scan(ctx, skill, role, export_file, slack_webhook):
    """Scan all accounts in the org, report by OU"""
    region = ctx.obj["region"]
    profile = ctx.obj["profile"]
    regions = get_regions(region, profile)

    skills_to_run = [SkillRegistry.get(skill)] if skill else list(SkillRegistry.all().values())
    skills_to_run = [s for s in skills_to_run if s]

    # Build org tree
    console.print("[cyan]Fetching organization structure...[/cyan]")
    org_tree = build_org_tree(profile)

    total_accounts = sum(len(ou["accounts"]) for ou in org_tree.values())
    console.print(Panel(
        f"[bold cyan]🤖 AWS Operations Agent — ORG SCAN[/bold cyan]\n"
        f"[dim]{len(org_tree)} OUs | {total_accounts} accounts | {len(regions)} regions | "
        f"Skills: {', '.join(s.name for s in skills_to_run)}[/dim]",
        box=box.DOUBLE, style="cyan"
    ))

    # Scan each account, grouped by OU
    import boto3
    ou_results = {}  # ou_name -> [(account_name, account_id, [SkillResult])]

    for ou_name, ou_info in org_tree.items():
        ou_results[ou_name] = []
        for acct in ou_info["accounts"]:
            aid = acct["id"]
            aname = acct["name"]
            console.print(f"\n[bold cyan]━━━ {ou_name} / {aname} ({aid}) ━━━[/bold cyan]")

            # Assume role into member account
            try:
                session = boto3.Session(profile_name=profile) if profile else boto3.Session()
                sts = session.client("sts")
                creds = sts.assume_role(
                    RoleArn=f"arn:aws:iam::{aid}:role/{role}",
                    RoleSessionName="OpsAgentOrgScan",
                    DurationSeconds=3600,
                )["Credentials"]
                member_session = boto3.Session(
                    aws_access_key_id=creds["AccessKeyId"],
                    aws_secret_access_key=creds["SecretAccessKey"],
                    aws_session_token=creds["SessionToken"],
                )
                # Create a temp profile-like mechanism by patching env
                import os
                os.environ["AWS_ACCESS_KEY_ID"] = creds["AccessKeyId"]
                os.environ["AWS_SECRET_ACCESS_KEY"] = creds["SecretAccessKey"]
                os.environ["AWS_SESSION_TOKEN"] = creds["SessionToken"]

                acct_results = []
                for s in skills_to_run:
                    console.print(f"  Running {s.name}...", end="")
                    result = s.scan(regions, profile=None, account_id=aid)
                    for f in result.findings:
                        f.account_id = aid
                    acct_results.append(result)
                    console.print(f" [green]{len(result.findings)} findings[/green]")

                ou_results[ou_name].append((aname, aid, acct_results))

            except Exception as e:
                console.print(f"  [red]Failed to assume role: {e}[/red]")
                ou_results[ou_name].append((aname, aid, []))
            finally:
                # Clean up env vars
                for key in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"]:
                    os.environ.pop(key, None)

    # Also scan management account
    console.print(f"\n[bold cyan]━━━ Management Account ━━━[/bold cyan]")
    mgmt_id = get_account_id(profile)
    mgmt_results = []
    for s in skills_to_run:
        console.print(f"  Running {s.name}...", end="")
        result = s.scan(regions, profile, account_id=mgmt_id)
        for f in result.findings:
            f.account_id = mgmt_id
        mgmt_results.append(result)
        console.print(f" [green]{len(result.findings)} findings[/green]")
    ou_results.setdefault("Management", []).append(("Management Account", mgmt_id, mgmt_results))

    # Print OU-level report
    _print_ou_report(ou_results, skills_to_run)

    if slack_webhook:
        # Send summary to Slack
        for ou_name, accounts in ou_results.items():
            for aname, aid, results in accounts:
                for r in results:
                    if r.findings:
                        notify_slack(slack_webhook, r)

    if export_file:
        _export_org(ou_results, export_file)




def _print_ou_report(ou_results, skills):
    """Print findings grouped by OU."""
    # OU summary table
    table = Table(title="[bold cyan]🤖 ORG-WIDE REPORT BY OU[/bold cyan]", box=box.DOUBLE_EDGE, show_lines=True)
    table.add_column("OU", style="cyan")
    table.add_column("Account")
    table.add_column("Findings", justify="right")
    table.add_column("Critical", justify="right")
    table.add_column("Impact/mo", justify="right", style="red")

    grand_findings = 0
    grand_critical = 0
    grand_impact = 0.0

    for ou_name in sorted(ou_results.keys()):
        accounts = ou_results[ou_name]
        for aname, aid, results in accounts:
            total_f = sum(len(r.findings) for r in results)
            total_c = sum(r.critical_count for r in results)
            total_i = sum(r.total_impact for r in results)
            grand_findings += total_f
            grand_critical += total_c
            grand_impact += total_i

            crit_str = f"[red]{total_c}[/red]" if total_c else "[green]0[/green]"
            table.add_row(ou_name, f"{aname}\n({aid})", str(total_f), crit_str, f"${total_i:,.0f}")

    table.add_row("", "", "", "", "")
    table.add_row("[bold]TOTAL[/bold]", "", f"[bold]{grand_findings}[/bold]",
                  f"[bold red]{grand_critical}[/bold red]", f"[bold red]${grand_impact:,.0f}/mo[/bold red]")
    console.print(table)

    # Tree visualization
    tree = Tree("[bold cyan]🤖 Organization Findings[/bold cyan]")
    for ou_name in sorted(ou_results.keys()):
        ou_node = tree.add(f"[cyan]{ou_name}[/cyan]")
        for aname, aid, results in ou_results[ou_name]:
            total_f = sum(len(r.findings) for r in results)
            total_i = sum(r.total_impact for r in results)
            total_c = sum(r.critical_count for r in results)
            color = "red" if total_c > 0 else "yellow" if total_f > 0 else "green"
            acct_node = ou_node.add(f"[{color}]{aname} ({aid}) — {total_f} findings, ${total_i:,.0f}/mo[/{color}]")
            for r in results:
                if r.findings:
                    skill_node = acct_node.add(f"[dim]{r.skill_name}: {len(r.findings)} findings[/dim]")
                    for f in r.findings[:5]:
                        emoji = SEVERITY_EMOJI.get(f.severity.value, "⚪")
                        skill_node.add(f"{emoji} {f.title}")
                    if len(r.findings) > 5:
                        skill_node.add(f"[dim]... +{len(r.findings)-5} more[/dim]")
    console.print(tree)


def _export_org(ou_results, export_file):
    report = {
        "agent": "aws-ops-agent",
        "scan_type": "org-wide",
        "scan_time": datetime.utcnow().isoformat(),
        "by_ou": {},
    }
    grand_findings = 0
    grand_impact = 0.0

    for ou_name, accounts in ou_results.items():
        ou_data = {"accounts": {}}
        for aname, aid, results in accounts:
            acct_data = {
                "name": aname,
                "findings_count": sum(len(r.findings) for r in results),
                "monthly_impact": sum(r.total_impact for r in results),
                "skills": {},
            }
            for r in results:
                acct_data["skills"][r.skill_name] = {
                    "findings_count": len(r.findings),
                    "monthly_impact": r.total_impact,
                    "findings": [f.to_dict() for f in r.findings],
                }
            grand_findings += acct_data["findings_count"]
            grand_impact += acct_data["monthly_impact"]
            ou_data["accounts"][aid] = acct_data
        report["by_ou"][ou_name] = ou_data

    report["summary"] = {
        "total_findings": grand_findings,
        "total_monthly_impact": round(grand_impact, 2),
    }

    with open(export_file, "w") as f:
        json.dump(report, f, indent=2, default=str)
    console.print(f"\n[green]Org report exported to {export_file}[/green]")


def _print_skill_result(result):
    if not result.findings:
        console.print(f"  [green]✓ No findings ({result.duration_seconds:.1f}s)[/green]")
        return

    console.print(f"  [yellow]{len(result.findings)} findings[/yellow] | "
                  f"Impact: [red]${result.total_impact:,.0f}/mo[/red] | "
                  f"Time: {result.duration_seconds:.1f}s")

    table = Table(box=box.ROUNDED, show_lines=True, padding=(0, 1))
    table.add_column("Sev", width=3, justify="center")
    table.add_column("Finding", style="cyan", max_width=40)
    table.add_column("Region", max_width=12)
    table.add_column("Resource", max_width=28)
    table.add_column("Impact/mo", justify="right", style="red")
    table.add_column("Action", style="yellow", max_width=35)

    for f in sorted(result.findings, key=lambda x: list(Severity).index(x.severity)):
        emoji = SEVERITY_EMOJI.get(f.severity.value, "⚪")
        table.add_row(
            emoji, f.title, f.region, f.resource_id,
            f"${f.monthly_impact:,.0f}" if f.monthly_impact else "-",
            f.recommended_action,
        )

    console.print(table)


def _print_summary(all_results):
    total_findings = sum(len(r.findings) for r in all_results)
    total_impact = sum(r.total_impact for r in all_results)
    total_critical = sum(r.critical_count for r in all_results)
    total_time = sum(r.duration_seconds for r in all_results)

    table = Table(box=box.DOUBLE_EDGE, show_lines=True)
    table.add_column("Skill", style="cyan")
    table.add_column("Findings", justify="right")
    table.add_column("Critical", justify="right")
    table.add_column("Impact/mo", justify="right", style="red")
    table.add_column("Time", justify="right")

    for r in all_results:
        crit_str = f"[red]{r.critical_count}[/red]" if r.critical_count else "[green]0[/green]"
        table.add_row(r.skill_name, str(len(r.findings)), crit_str,
                      f"${r.total_impact:,.0f}", f"{r.duration_seconds:.1f}s")

    table.add_row("", "", "", "", "")
    table.add_row("[bold]TOTAL[/bold]", f"[bold]{total_findings}[/bold]",
                  f"[bold red]{total_critical}[/bold red]",
                  f"[bold red]${total_impact:,.0f}/mo[/bold red]",
                  f"[bold]{total_time:.1f}s[/bold]")

    console.print(Panel(table, title="[bold cyan]🤖 OPERATIONS SUMMARY[/bold cyan]", box=box.DOUBLE))


def _export(all_results, export_file, account_id):
    report = {
        "agent": "aws-ops-agent",
        "version": "0.1.0",
        "scan_time": datetime.utcnow().isoformat(),
        "account_id": account_id,
        "summary": {
            "total_findings": sum(len(r.findings) for r in all_results),
            "total_monthly_impact": sum(r.total_impact for r in all_results),
            "total_critical": sum(r.critical_count for r in all_results),
        },
        "skills": {
            r.skill_name: {
                "findings_count": len(r.findings),
                "monthly_impact": r.total_impact,
                "duration_seconds": r.duration_seconds,
                "findings": [f.to_dict() for f in r.findings],
                "errors": r.errors,
            }
            for r in all_results
        },
    }
    with open(export_file, "w") as f:
        json.dump(report, f, indent=2, default=str)
    console.print(f"\n[green]Report exported to {export_file}[/green]")


@cli.command("dashboard")
@click.option("--host", default="127.0.0.1", help="Server host")
@click.option("--port", default=8080, type=int, help="Server port")
@click.option("--api-key", default=None, help="API key for dashboard auth (or set OPS_AGENT_API_KEY env var)")
@click.pass_context
def dashboard(ctx, host, port, api_key):
    """Launch the web dashboard"""
    import webbrowser
    import uvicorn
    from ops_agent.dashboard.server import create_app
    from ops_agent.dashboard.security import generate_api_key

    profile = ctx.obj["profile"]
    # Auto-generate key if not provided and not in env
    effective_key = api_key or os.environ.get("OPS_AGENT_API_KEY")
    if not effective_key and host != "127.0.0.1" and host != "localhost":
        effective_key = generate_api_key()
        console.print(f"[yellow]⚠ Non-localhost deployment detected. Auto-generated API key:[/yellow]")
        console.print(f"[bold green]{effective_key}[/bold green]")
        console.print(f"[dim]Pass this key in the X-API-Key header for API requests.[/dim]")

    app = create_app(profile=profile, api_key=effective_key)
    auth_status = f"API Key: {'enabled' if effective_key else 'disabled (localhost only)'}"
    console.print(Panel(
        f"[bold cyan]⚡🔧 AWS Ops Agent Dashboard[/bold cyan]\n"
        f"[dim]http://{host}:{port} | Profile: {profile or 'default'} | {auth_status}[/dim]",
        box=box.DOUBLE, style="cyan"
    ))
    webbrowser.open(f"http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    cli()
