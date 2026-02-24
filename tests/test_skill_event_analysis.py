"""Tests for Event Analysis skill."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from ops_agent.skills.event_analysis import EventAnalysisSkill, HIGH_RISK_EVENTS
from ops_agent.core import Severity


@pytest.fixture
def skill():
    return EventAnalysisSkill()


class TestEventAnalysisMetadata:
    def test_name(self, skill):
        assert skill.name == "event-analysis"

    def test_high_risk_events_defined(self):
        assert "DeleteSecurityGroup" in HIGH_RISK_EVENTS
        assert "TerminateInstances" in HIGH_RISK_EVENTS
        assert "PutBucketPolicy" in HIGH_RISK_EVENTS


class TestCloudTrail:
    @patch("ops_agent.skills.event_analysis.get_client")
    def test_finds_high_risk_events(self, mock_gc):
        ct_mock = MagicMock()
        ct_mock.lookup_events.return_value = {
            "Events": [{
                "EventName": "DeleteSecurityGroup",
                "Username": "admin-user",
                "Resources": [{"ResourceName": "sg-deleted"}],
                "EventTime": datetime.now(timezone.utc),
            }]
        }
        mock_gc.return_value = ct_mock

        skill = EventAnalysisSkill()
        findings = skill._check_cloudtrail("us-east-1", "test", 24)
        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH  # Delete* events are HIGH

    @patch("ops_agent.skills.event_analysis.get_client")
    def test_non_risky_event_ignored(self, mock_gc):
        ct_mock = MagicMock()
        ct_mock.lookup_events.return_value = {
            "Events": [{"EventName": "DescribeInstances", "Username": "reader"}]
        }
        mock_gc.return_value = ct_mock

        skill = EventAnalysisSkill()
        findings = skill._check_cloudtrail("us-east-1", "test", 24)
        assert len(findings) == 0


class TestRootUsage:
    @patch("ops_agent.skills.event_analysis.get_client")
    def test_finds_root_activity(self, mock_gc):
        ct_mock = MagicMock()
        ct_mock.lookup_events.return_value = {
            "Events": [{
                "EventName": "ConsoleLogin",
                "EventTime": datetime.now(timezone.utc),
            }]
        }
        mock_gc.return_value = ct_mock

        skill = EventAnalysisSkill()
        findings = skill._check_root_usage("us-east-1", "test", 24)
        assert len(findings) == 1
        assert findings[0].severity == Severity.CRITICAL


class TestUnauthorized:
    @patch("ops_agent.skills.event_analysis.get_client")
    def test_detects_many_denied(self, mock_gc):
        ct_mock = MagicMock()
        events = []
        for i in range(15):
            events.append({
                "EventName": f"SomeAction{i}",
                "Username": "bad-actor",
                "CloudTrailEvent": '{"errorCode":"AccessDenied"}',
            })
        ct_mock.lookup_events.return_value = {"Events": events}
        mock_gc.return_value = ct_mock

        skill = EventAnalysisSkill()
        findings = skill._check_unauthorized("us-east-1", "test", 24)
        assert len(findings) == 1
        assert findings[0].severity == Severity.MEDIUM  # 10 < 15 < 50

    @patch("ops_agent.skills.event_analysis.get_client")
    def test_few_denied_not_flagged(self, mock_gc):
        ct_mock = MagicMock()
        events = [
            {"EventName": "SomeAction", "Username": "user", "CloudTrailEvent": '{"errorCode":"AccessDenied"}'}
        ]
        ct_mock.lookup_events.return_value = {"Events": events}
        mock_gc.return_value = ct_mock

        skill = EventAnalysisSkill()
        findings = skill._check_unauthorized("us-east-1", "test", 24)
        assert len(findings) == 0


class TestConfigCompliance:
    @patch("ops_agent.skills.event_analysis.get_client")
    def test_finds_non_compliant_rules(self, mock_gc):
        config_mock = MagicMock()
        config_mock.describe_compliance_by_config_rule.return_value = {
            "ComplianceByConfigRules": [
                {"ConfigRuleName": "s3-bucket-ssl-requests-only"},
                {"ConfigRuleName": "ec2-instance-no-public-ip"},
            ]
        }
        mock_gc.return_value = config_mock

        skill = EventAnalysisSkill()
        findings = skill._check_config_compliance("us-east-1", "test")
        assert len(findings) == 2
        assert findings[0].severity == Severity.MEDIUM
