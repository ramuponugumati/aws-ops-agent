"""Tests for Health Monitor skill."""
import pytest
from unittest.mock import patch, MagicMock
from ops_agent.skills.health_monitor import HealthMonitorSkill
from ops_agent.core import Severity


@pytest.fixture
def skill():
    return HealthMonitorSkill()


class TestHealthMonitorMetadata:
    def test_name(self, skill):
        assert skill.name == "health-monitor"


class TestHealthEvents:
    @patch("ops_agent.skills.health_monitor.get_client")
    def test_finds_open_issue(self, mock_gc):
        health_mock = MagicMock()
        health_mock.describe_events.return_value = {
            "events": [{
                "arn": "arn:aws:health:us-east-1::event/EC2/issue/123",
                "service": "EC2",
                "eventTypeCategory": "issue",
                "statusCode": "open",
                "region": "us-east-1",
            }]
        }
        health_mock.describe_event_details.return_value = {
            "successfulSet": [{"eventDescription": {"latestDescription": "EC2 connectivity issues"}}]
        }
        health_mock.describe_affected_entities.return_value = {
            "entities": [{"entityValue": "i-affected1"}]
        }
        mock_gc.return_value = health_mock

        skill = HealthMonitorSkill()
        findings = skill._check_health_events("test", ["us-east-1"])
        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH

    @patch("ops_agent.skills.health_monitor.get_client")
    def test_scheduled_change_medium(self, mock_gc):
        health_mock = MagicMock()
        health_mock.describe_events.return_value = {
            "events": [{
                "arn": "arn:...",
                "service": "RDS",
                "eventTypeCategory": "scheduledChange",
                "statusCode": "upcoming",
                "region": "us-east-1",
            }]
        }
        health_mock.describe_event_details.return_value = {"successfulSet": []}
        health_mock.describe_affected_entities.return_value = {"entities": []}
        mock_gc.return_value = health_mock

        skill = HealthMonitorSkill()
        findings = skill._check_health_events("test", ["us-east-1"])
        assert len(findings) == 1
        assert findings[0].severity == Severity.MEDIUM

    @patch("ops_agent.skills.health_monitor.get_client")
    def test_subscription_required(self, mock_gc):
        health_mock = MagicMock()
        health_mock.describe_events.side_effect = type(
            "SubscriptionRequiredException", (Exception,), {}
        )("Need Business support")
        health_mock.exceptions.SubscriptionRequiredException = type(
            "SubscriptionRequiredException", (Exception,), {}
        )
        # Re-raise the right type
        health_mock.describe_events.side_effect = health_mock.exceptions.SubscriptionRequiredException("Need Business support")
        mock_gc.return_value = health_mock

        skill = HealthMonitorSkill()
        findings = skill._check_health_events("test", ["us-east-1"])
        assert len(findings) == 1
        assert findings[0].severity == Severity.INFO
        assert "Business" in findings[0].title


class TestTrustedAdvisor:
    @patch("ops_agent.skills.health_monitor.get_client")
    def test_finds_warning_checks(self, mock_gc):
        ta_mock = MagicMock()
        ta_mock.describe_trusted_advisor_checks.return_value = {
            "checks": [
                {"id": "chk-1", "name": "S3 Bucket Permissions", "category": "security"},
                {"id": "chk-2", "name": "Low Utilization EC2", "category": "cost_optimizing"},
            ]
        }
        ta_mock.describe_trusted_advisor_check_result.side_effect = [
            {"result": {"status": "warning", "flaggedResources": [{"id": "r1"}, {"id": "r2"}]}},
            {"result": {"status": "error", "flaggedResources": [{"id": "r3"}]}},
        ]
        mock_gc.return_value = ta_mock

        skill = HealthMonitorSkill()
        findings = skill._check_trusted_advisor("test")
        assert len(findings) == 2
        assert findings[0].severity == Severity.MEDIUM  # warning
        assert findings[1].severity == Severity.HIGH  # error
