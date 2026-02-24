"""Cost Anomaly Detective — detects spending spikes, attributes root cause, projects impact."""
import time
from datetime import datetime, timedelta, timezone
from ops_agent.core import BaseSkill, SkillResult, Finding, Severity
from ops_agent.aws_client import get_client, get_account_id, get_regions, parallel_regions


class CostAnomalySkill(BaseSkill):
    name = "cost-anomaly"
    description = "Detect cost spikes, attribute root cause, project monthly impact"
    version = "0.1.0"

    def scan(self, regions, profile=None, account_id=None, **kwargs) -> SkillResult:
        start = time.time()
        findings = []
        errors = []

        acct = account_id or get_account_id(profile)

        # 1. Check AWS Cost Anomaly Detection service
        try:
            findings.extend(self._check_cost_anomalies(profile))
        except Exception as e:
            errors.append(f"Cost Anomaly Detection: {e}")

        # 2. Compare this week vs last week by service
        try:
            findings.extend(self._check_week_over_week(profile))
        except Exception as e:
            errors.append(f"Week-over-week: {e}")

        # 3. Check for unexpected new services
        try:
            findings.extend(self._check_new_services(profile))
        except Exception as e:
            errors.append(f"New services: {e}")

        for f in findings:
            f.account_id = acct

        return SkillResult(
            skill_name=self.name,
            findings=findings,
            duration_seconds=time.time() - start,
            accounts_scanned=1,
            regions_scanned=len(regions),
            errors=errors,
        )

    def _check_cost_anomalies(self, profile):
        """Pull from AWS Cost Anomaly Detection service."""
        ce = get_client("ce", "us-east-1", profile)
        findings = []

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=14)

        try:
            resp = ce.get_anomalies(
                DateInterval={"StartDate": start.strftime("%Y-%m-%d"), "EndDate": end.strftime("%Y-%m-%d")},
                MaxResults=20,
            )
            for anomaly in resp.get("Anomalies", []):
                impact = anomaly.get("Impact", {})
                total = impact.get("TotalImpact", 0)
                if total < 10:
                    continue

                severity = Severity.CRITICAL if total > 1000 else Severity.HIGH if total > 100 else Severity.MEDIUM
                root_causes = anomaly.get("RootCauses", [])
                cause_str = "; ".join([
                    f"{rc.get('Service', '?')}/{rc.get('Region', '?')}/{rc.get('UsageType', '?')}"
                    for rc in root_causes[:3]
                ]) or "Unknown"

                findings.append(Finding(
                    skill=self.name,
                    title=f"Cost anomaly: ${total:,.0f} impact",
                    severity=severity,
                    description=f"Root cause: {cause_str}",
                    monthly_impact=total,
                    recommended_action="Investigate root cause and determine if expected",
                    metadata={"anomaly_id": anomaly.get("AnomalyId"), "root_causes": root_causes},
                ))
        except Exception:
            pass  # Cost Anomaly Detection may not be enabled

        return findings

    def _check_week_over_week(self, profile):
        """Compare this week's spend vs last week by service."""
        ce = get_client("ce", "us-east-1", profile)
        findings = []

        today = datetime.now(timezone.utc).date()
        this_week_start = today - timedelta(days=today.weekday())
        last_week_start = this_week_start - timedelta(days=7)
        last_week_end = this_week_start

        # Get last week
        lw = ce.get_cost_and_usage(
            TimePeriod={"Start": last_week_start.isoformat(), "End": last_week_end.isoformat()},
            Granularity="DAILY", Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        # Get this week (partial)
        days_this_week = (today - this_week_start).days or 1
        tw = ce.get_cost_and_usage(
            TimePeriod={"Start": this_week_start.isoformat(), "End": today.isoformat()},
            Granularity="DAILY", Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        # Aggregate by service
        def _agg(results):
            totals = {}
            for period in results.get("ResultsByTime", []):
                for group in period.get("Groups", []):
                    svc = group["Keys"][0]
                    amt = float(group["Metrics"]["UnblendedCost"]["Amount"])
                    totals[svc] = totals.get(svc, 0) + amt
            return totals

        lw_totals = _agg(lw)
        tw_totals = _agg(tw)

        # Normalize this week to 7-day projection
        for svc, tw_cost in tw_totals.items():
            projected = (tw_cost / days_this_week) * 7 if days_this_week > 0 else 0
            lw_cost = lw_totals.get(svc, 0)

            if lw_cost < 10:
                continue

            pct_change = ((projected - lw_cost) / lw_cost * 100) if lw_cost > 0 else 0
            abs_change = projected - lw_cost

            if pct_change > 25 and abs_change > 50:
                severity = Severity.HIGH if pct_change > 50 else Severity.MEDIUM
                monthly_impact = abs_change * 4.3  # weekly to monthly

                findings.append(Finding(
                    skill=self.name,
                    title=f"{svc}: +{pct_change:.0f}% week-over-week",
                    severity=severity,
                    description=(
                        f"Last week: ${lw_cost:,.0f} | This week (projected): ${projected:,.0f} | "
                        f"Change: +${abs_change:,.0f}/week"
                    ),
                    monthly_impact=round(monthly_impact, 2),
                    recommended_action="Review usage increase — expected growth or anomaly?",
                    metadata={"service": svc, "last_week": lw_cost, "this_week_projected": projected,
                              "pct_change": pct_change},
                ))

        return sorted(findings, key=lambda f: -f.monthly_impact)

    def _check_new_services(self, profile):
        """Detect services that appeared this month but weren't used last month."""
        ce = get_client("ce", "us-east-1", profile)
        findings = []

        today = datetime.now(timezone.utc).date()
        this_month_start = today.replace(day=1)
        last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

        lm = ce.get_cost_and_usage(
            TimePeriod={"Start": last_month_start.isoformat(), "End": this_month_start.isoformat()},
            Granularity="MONTHLY", Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        tm = ce.get_cost_and_usage(
            TimePeriod={"Start": this_month_start.isoformat(), "End": today.isoformat()},
            Granularity="MONTHLY", Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        lm_services = set()
        for period in lm.get("ResultsByTime", []):
            for group in period.get("Groups", []):
                if float(group["Metrics"]["UnblendedCost"]["Amount"]) > 1:
                    lm_services.add(group["Keys"][0])

        for period in tm.get("ResultsByTime", []):
            for group in period.get("Groups", []):
                svc = group["Keys"][0]
                cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
                if svc not in lm_services and cost > 10:
                    findings.append(Finding(
                        skill=self.name,
                        title=f"New service detected: {svc}",
                        severity=Severity.LOW,
                        description=f"${cost:,.0f} this month — not used last month",
                        monthly_impact=round(cost, 2),
                        recommended_action="Verify this is intentional new usage",
                        metadata={"service": svc, "cost": cost},
                    ))

        return findings
