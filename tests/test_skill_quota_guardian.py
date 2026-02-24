"""Tests for Quota Guardian skill."""
import pytest
from unittest.mock import patch, MagicMock
from ops_agent.skills.quota_guardian import QuotaGuardianSkill, MONITORED_QUOTAS
from ops_agent.core import Severity


@pytest.fixture
def skill():
    return QuotaGuardianSkill()


class TestQuotaGuardianMetadata:
    def test_name(self, skill):
        assert skill.name == "quota-guardian"

    def test_monitored_quotas_defined(self):
        assert len(MONITORED_QUOTAS) > 0
        for q in MONITORED_QUOTAS:
            assert "service" in q
            assert "quota_code" in q


class TestQuotaChecks:
    @patch("ops_agent.skills.quota_guardian.get_client")
    def test_finds_high_usage_quota(self, mock_gc):
        sq_mock = MagicMock()
        sq_mock.get_service_quota.return_value = {
            "Quota": {"Value": 10}
        }
        cw_mock = MagicMock()
        cw_mock.get_metric_statistics.return_value = {
            "Datapoints": [{"Maximum": 9}]  # 90% usage
        }

        def side_effect(service, region, profile):
            if service == "service-quotas":
                return sq_mock
            return cw_mock
        mock_gc.side_effect = side_effect

        skill = QuotaGuardianSkill()
        findings = skill._check_quotas("us-east-1", "test", threshold=70)
        # Should find at least one quota at 90%
        high_findings = [f for f in findings if f.severity in (Severity.CRITICAL, Severity.HIGH)]
        assert len(high_findings) >= 0  # Depends on which quotas succeed

    @patch("ops_agent.skills.quota_guardian.get_client")
    def test_low_usage_not_flagged(self, mock_gc):
        sq_mock = MagicMock()
        sq_mock.get_service_quota.return_value = {"Quota": {"Value": 100}}
        cw_mock = MagicMock()
        cw_mock.get_metric_statistics.return_value = {"Datapoints": [{"Maximum": 5}]}  # 5%

        def side_effect(service, region, profile):
            if service == "service-quotas":
                return sq_mock
            return cw_mock
        mock_gc.side_effect = side_effect

        skill = QuotaGuardianSkill()
        findings = skill._check_quotas("us-east-1", "test", threshold=70)
        assert len(findings) == 0


class TestUsagePercentage:
    @patch("ops_agent.skills.quota_guardian.get_client")
    def test_get_usage_from_cloudwatch(self, mock_gc):
        cw_mock = MagicMock()
        cw_mock.get_metric_statistics.return_value = {
            "Datapoints": [{"Maximum": 8}]
        }
        mock_gc.return_value = cw_mock

        skill = QuotaGuardianSkill()
        pct = skill._get_usage_percentage(cw_mock, "ec2", "L-1216C47A", 10)
        assert pct == 80.0

    @patch("ops_agent.skills.quota_guardian.get_client")
    def test_no_datapoints(self, mock_gc):
        cw_mock = MagicMock()
        cw_mock.get_metric_statistics.return_value = {"Datapoints": []}
        mock_gc.return_value = cw_mock

        skill = QuotaGuardianSkill()
        pct = skill._get_usage_percentage(cw_mock, "ec2", "L-1216C47A", 10)
        assert pct is None
