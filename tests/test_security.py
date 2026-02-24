"""Tests for security middleware and utilities."""
import pytest
import time
from unittest.mock import MagicMock, patch
from ops_agent.dashboard.security import (
    generate_api_key, APIKeyMiddleware, RateLimiter,
    sanitize_chat_message, validate_findings_payload,
    AuditLogger, MAX_CHAT_MESSAGE_LENGTH, MAX_FINDINGS_COUNT,
)


class TestGenerateAPIKey:
    def test_generates_key(self):
        key = generate_api_key()
        assert key.startswith("ops-")
        assert len(key) > 20

    def test_keys_are_unique(self):
        k1 = generate_api_key()
        k2 = generate_api_key()
        assert k1 != k2


class TestRateLimiter:
    def test_allows_normal_traffic(self):
        limiter = RateLimiter(requests_per_minute=30, burst=30)
        for _ in range(10):
            assert limiter.check("1.2.3.4") is True

    def test_blocks_over_rpm(self):
        limiter = RateLimiter(requests_per_minute=5, burst=100)
        for _ in range(5):
            limiter.check("1.2.3.4")
        assert limiter.check("1.2.3.4") is False

    def test_different_ips_independent(self):
        limiter = RateLimiter(requests_per_minute=2, burst=100)
        limiter.check("1.1.1.1")
        limiter.check("1.1.1.1")
        assert limiter.check("1.1.1.1") is False
        assert limiter.check("2.2.2.2") is True  # different IP

    def test_burst_protection(self):
        limiter = RateLimiter(requests_per_minute=100, burst=3)
        # Rapid fire should hit burst limit
        assert limiter.check("1.2.3.4") is True
        assert limiter.check("1.2.3.4") is True
        assert limiter.check("1.2.3.4") is True
        assert limiter.check("1.2.3.4") is False


class TestSanitizeChatMessage:
    def test_normal_message(self):
        assert sanitize_chat_message("Hello, what are my findings?") == "Hello, what are my findings?"

    def test_strips_control_chars(self):
        result = sanitize_chat_message("Hello\x00\x01\x02World")
        assert "\x00" not in result
        assert "HelloWorld" == result

    def test_preserves_newlines(self):
        result = sanitize_chat_message("Line 1\nLine 2\tTabbed")
        assert "\n" in result
        assert "\t" in result

    def test_empty_message_raises(self):
        with pytest.raises(ValueError, match="empty"):
            sanitize_chat_message("")

    def test_too_long_raises(self):
        long_msg = "x" * (MAX_CHAT_MESSAGE_LENGTH + 1)
        with pytest.raises(ValueError, match="too long"):
            sanitize_chat_message(long_msg)

    def test_max_length_ok(self):
        msg = "x" * MAX_CHAT_MESSAGE_LENGTH
        assert len(sanitize_chat_message(msg)) == MAX_CHAT_MESSAGE_LENGTH

    def test_strips_whitespace(self):
        assert sanitize_chat_message("  hello  ") == "hello"


class TestValidateFindingsPayload:
    def test_none_returns_none(self):
        assert validate_findings_payload(None) is None

    def test_normal_list_passes(self):
        findings = [{"title": f"f{i}"} for i in range(10)]
        assert len(validate_findings_payload(findings)) == 10

    def test_truncates_oversized(self):
        findings = [{"title": f"f{i}"} for i in range(MAX_FINDINGS_COUNT + 100)]
        result = validate_findings_payload(findings)
        assert len(result) == MAX_FINDINGS_COUNT


class TestAuditLogger:
    def test_log_remediation(self, tmp_path):
        log_file = str(tmp_path / "audit.log")
        audit = AuditLogger(log_file=log_file)
        audit.log_remediation(
            action="delete_ebs_volume", resource_id="vol-abc",
            region="us-east-1", skill="zombie-hunter",
            success=True, message="Deleted", client_ip="127.0.0.1",
        )
        with open(log_file) as f:
            content = f.read()
        assert "REMEDIATION" in content
        assert "vol-abc" in content
        assert "delete_ebs_volume" in content
        assert "127.0.0.1" in content

    def test_log_chat(self, tmp_path):
        log_file = str(tmp_path / "audit.log")
        # Force a fresh logger by clearing handlers
        import logging
        audit_logger = logging.getLogger("ops_agent.audit")
        audit_logger.handlers.clear()
        audit = AuditLogger(log_file=log_file)
        audit.log_chat("10.0.0.1", 150)
        for h in audit._logger.handlers:
            h.flush()
        with open(log_file) as f:
            content = f.read()
        assert "CHAT" in content
        assert "10.0.0.1" in content
