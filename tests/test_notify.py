"""Tests for notification handlers."""
import pytest
import json
from unittest.mock import patch, MagicMock
from ops_agent.notify import notify_slack, notify_sns, notify_console
from ops_agent.core import Finding, Severity, SkillResult


@pytest.fixture
def result_with_findings():
    findings = [
        Finding(skill="test", title="Critical issue", severity=Severity.CRITICAL,
                description="Bad thing", resource_id="r-1", region="us-east-1",
                account_id="123", monthly_impact=500),
        Finding(skill="test", title="Low issue", severity=Severity.LOW,
                description="Minor thing", resource_id="r-2", region="us-west-2",
                account_id="123", monthly_impact=10),
    ]
    return SkillResult(skill_name="test-skill", findings=findings)


@pytest.fixture
def empty_result():
    return SkillResult(skill_name="test-skill", findings=[])


class TestNotifySlack:
    @patch("ops_agent.notify.requests.post")
    def test_sends_slack_message(self, mock_post, result_with_findings):
        notify_slack("https://hooks.slack.com/test", result_with_findings)
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert "blocks" in call_kwargs[1]["json"]

    @patch("ops_agent.notify.requests.post")
    def test_skips_empty_results(self, mock_post, empty_result):
        notify_slack("https://hooks.slack.com/test", empty_result)
        mock_post.assert_not_called()

    @patch("ops_agent.notify.requests.post")
    def test_handles_post_failure(self, mock_post, result_with_findings):
        mock_post.side_effect = Exception("Connection refused")
        # Should not raise
        notify_slack("https://hooks.slack.com/test", result_with_findings)

    @patch("ops_agent.notify.requests.post")
    def test_truncates_large_findings(self, mock_post):
        findings = [
            Finding(skill="test", title=f"Finding {i}", severity=Severity.LOW,
                    description="d", resource_id=f"r-{i}", region="us-east-1",
                    account_id="123", monthly_impact=1)
            for i in range(15)
        ]
        result = SkillResult(skill_name="test", findings=findings)
        notify_slack("https://hooks.slack.com/test", result)
        call_kwargs = mock_post.call_args
        blocks = call_kwargs[1]["json"]["blocks"]
        # Should have "... and N more" block
        last_text = blocks[-1].get("text", {}).get("text", "")
        assert "more" in last_text


class TestNotifySNS:
    @patch("boto3.Session")
    def test_publishes_to_sns(self, mock_session_cls, result_with_findings):
        sns_mock = MagicMock()
        session_mock = MagicMock()
        session_mock.client.return_value = sns_mock
        mock_session_cls.return_value = session_mock

        notify_sns("arn:aws:sns:us-east-1:123:my-topic", result_with_findings, "test")
        sns_mock.publish.assert_called_once()
        call_kwargs = sns_mock.publish.call_args[1]
        assert call_kwargs["TopicArn"] == "arn:aws:sns:us-east-1:123:my-topic"
        msg = json.loads(call_kwargs["Message"])
        assert msg["findings_count"] == 2

    def test_skips_empty_results(self, empty_result):
        # notify_sns returns early if no findings — no boto3 call needed
        notify_sns("arn:aws:sns:us-east-1:123:my-topic", empty_result)

    @patch("boto3.Session")
    def test_handles_publish_failure(self, mock_session_cls, result_with_findings):
        sns_mock = MagicMock()
        sns_mock.publish.side_effect = Exception("Access denied")
        session_mock = MagicMock()
        session_mock.client.return_value = sns_mock
        mock_session_cls.return_value = session_mock
        # Should not raise
        notify_sns("arn:aws:sns:us-east-1:123:my-topic", result_with_findings)


class TestNotifyConsole:
    def test_console_noop(self):
        result = SkillResult(skill_name="test")
        notify_console(result)  # Should not raise
