"""Tests for chat handler."""
import pytest
import json
from unittest.mock import patch, MagicMock
from ops_agent.dashboard.chat import (
    handle_chat, _format_findings_context, _is_remediable,
    BedrockUnavailableError, SYSTEM_PROMPT,
)


class TestFormatFindingsContext:
    def test_empty_findings(self):
        ctx = _format_findings_context([])
        assert "No scan findings available" in ctx

    def test_with_findings(self, sample_findings_list):
        ctx = _format_findings_context(sample_findings_list)
        assert "3 total" in ctx
        assert "HIGH" in ctx
        assert "MEDIUM" in ctx
        assert "LOW" in ctx

    def test_skills_run_context(self):
        ctx = _format_findings_context([], skills_run=["zombie-hunter"], skills_not_run=["cost-anomaly"])
        assert "zombie-hunter" in ctx
        assert "cost-anomaly" in ctx
        assert "NOT yet run" in ctx

    def test_remediation_markers(self, sample_findings_list):
        ctx = _format_findings_context(sample_findings_list)
        assert "[HAS FIX IT BUTTON]" in ctx  # EBS and open port are remediable

    def test_impact_summary(self, sample_findings_list):
        ctx = _format_findings_context(sample_findings_list)
        assert "$81" in ctx  # 8 + 73 = 81


class TestIsRemediable:
    def test_ebs_is_remediable(self):
        assert _is_remediable({"skill": "zombie-hunter", "title": "Unattached EBS: vol-abc"}) is True

    def test_open_port_is_remediable(self):
        assert _is_remediable({"skill": "security-posture", "title": "Open port 22 to 0.0.0.0/0: sg-abc"}) is True

    def test_cost_anomaly_not_remediable(self):
        assert _is_remediable({"skill": "cost-anomaly", "title": "Cost anomaly: $500"}) is False

    def test_empty_finding(self):
        assert _is_remediable({}) is False


class TestSystemPrompt:
    def test_system_prompt_exists(self):
        assert len(SYSTEM_PROMPT) > 100

    def test_system_prompt_has_rules(self):
        assert "RULES" in SYSTEM_PROMPT
        assert "NEVER fabricate" in SYSTEM_PROMPT

    def test_system_prompt_has_skill_icons(self):
        assert "💰" in SYSTEM_PROMPT
        assert "🧟" in SYSTEM_PROMPT
        assert "🛡️" in SYSTEM_PROMPT


class TestHandleChat:
    @patch("ops_agent.dashboard.chat.get_client")
    def test_successful_chat(self, mock_gc):
        bedrock_mock = MagicMock()
        response_body = MagicMock()
        response_body.read.return_value = json.dumps({
            "content": [{"text": "Here are your findings..."}]
        }).encode()
        bedrock_mock.invoke_model.return_value = {"body": response_body}
        mock_gc.return_value = bedrock_mock

        result = handle_chat("What are my findings?", [], "test")
        assert result == "Here are your findings..."
        bedrock_mock.invoke_model.assert_called_once()

    @patch("ops_agent.dashboard.chat.get_client")
    def test_bedrock_access_denied(self, mock_gc):
        bedrock_mock = MagicMock()
        bedrock_mock.invoke_model.side_effect = Exception("AccessDenied: not authorized")
        mock_gc.return_value = bedrock_mock

        with pytest.raises(BedrockUnavailableError):
            handle_chat("hello", [], "test")

    @patch("ops_agent.dashboard.chat.get_client")
    def test_bedrock_connection_failure(self, mock_gc):
        mock_gc.side_effect = Exception("Cannot connect")

        with pytest.raises(BedrockUnavailableError):
            handle_chat("hello", [], "test")

    @patch("ops_agent.dashboard.chat.get_client")
    def test_findings_passed_to_bedrock(self, mock_gc):
        bedrock_mock = MagicMock()
        response_body = MagicMock()
        response_body.read.return_value = json.dumps({
            "content": [{"text": "Analysis..."}]
        }).encode()
        bedrock_mock.invoke_model.return_value = {"body": response_body}
        mock_gc.return_value = bedrock_mock

        findings = [{"skill": "zombie-hunter", "title": "Idle EC2", "severity": "medium"}]
        handle_chat("analyze", findings, "test", skills_run=["zombie-hunter"])

        # Verify the findings context was included in the message
        call_args = bedrock_mock.invoke_model.call_args
        body = json.loads(call_args[1]["body"])
        assert "zombie-hunter" in body["messages"][0]["content"]
