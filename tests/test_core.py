"""Tests for core framework — Finding, SkillResult, SkillRegistry, BaseSkill."""
import pytest
from datetime import datetime, timezone
from ops_agent.core import Finding, Severity, ActionStatus, SkillResult, BaseSkill, SkillRegistry


class TestSeverity:
    def test_severity_values(self):
        assert Severity.CRITICAL.value == "critical"
        assert Severity.HIGH.value == "high"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.LOW.value == "low"
        assert Severity.INFO.value == "info"

    def test_severity_ordering(self):
        ordered = list(Severity)
        assert ordered[0] == Severity.CRITICAL
        assert ordered[-1] == Severity.INFO


class TestActionStatus:
    def test_action_status_values(self):
        assert ActionStatus.PENDING.value == "pending_approval"
        assert ActionStatus.APPROVED.value == "approved"
        assert ActionStatus.EXECUTED.value == "executed"
        assert ActionStatus.SKIPPED.value == "skipped"


class TestFinding:
    def test_finding_defaults(self):
        f = Finding(skill="test", title="t", severity=Severity.LOW, description="d")
        assert f.resource_id == ""
        assert f.account_id == ""
        assert f.region == ""
        assert f.monthly_impact == 0.0
        assert f.recommended_action == ""
        assert f.action_status == ActionStatus.PENDING
        assert f.auto_remediate is False
        assert f.metadata == {}
        assert f.timestamp  # auto-generated

    def test_finding_to_dict(self, sample_finding):
        d = sample_finding.to_dict()
        assert d["severity"] == "high"
        assert d["action_status"] == "pending_approval"
        assert d["skill"] == "test-skill"
        assert d["resource_id"] == "i-1234567890abcdef0"
        assert d["monthly_impact"] == 100.0
        assert isinstance(d["metadata"], dict)

    def test_finding_to_dict_serializes_enums(self):
        f = Finding(skill="s", title="t", severity=Severity.CRITICAL, description="d")
        d = f.to_dict()
        assert isinstance(d["severity"], str)
        assert isinstance(d["action_status"], str)

    def test_finding_timestamp_is_iso(self):
        f = Finding(skill="s", title="t", severity=Severity.LOW, description="d")
        # Should parse without error
        datetime.fromisoformat(f.timestamp)


class TestSkillResult:
    def test_empty_result(self):
        r = SkillResult(skill_name="test")
        assert r.findings == []
        assert r.total_impact == 0
        assert r.critical_count == 0
        assert r.duration_seconds == 0.0
        assert r.errors == []

    def test_total_impact(self):
        findings = [
            Finding(skill="s", title="a", severity=Severity.LOW, description="d", monthly_impact=50.0),
            Finding(skill="s", title="b", severity=Severity.LOW, description="d", monthly_impact=30.0),
        ]
        r = SkillResult(skill_name="test", findings=findings)
        assert r.total_impact == 80.0

    def test_critical_count(self):
        findings = [
            Finding(skill="s", title="a", severity=Severity.CRITICAL, description="d"),
            Finding(skill="s", title="b", severity=Severity.HIGH, description="d"),
            Finding(skill="s", title="c", severity=Severity.CRITICAL, description="d"),
        ]
        r = SkillResult(skill_name="test", findings=findings)
        assert r.critical_count == 2

    def test_result_with_errors(self):
        r = SkillResult(skill_name="test", errors=["err1", "err2"])
        assert len(r.errors) == 2


class TestSkillRegistry:
    def test_register_and_get(self):
        class DummySkill(BaseSkill):
            name = "dummy-test-skill"
            description = "test"
            version = "0.0.1"
            def scan(self, regions, profile=None, account_id=None, **kwargs):
                return SkillResult(skill_name=self.name)

        skill = DummySkill()
        SkillRegistry.register(skill)
        assert SkillRegistry.get("dummy-test-skill") is skill
        assert "dummy-test-skill" in SkillRegistry.names()
        # Cleanup
        del SkillRegistry._skills["dummy-test-skill"]

    def test_get_nonexistent(self):
        assert SkillRegistry.get("nonexistent-skill-xyz") is None

    def test_all_returns_dict(self):
        result = SkillRegistry.all()
        assert isinstance(result, dict)

    def test_names_returns_list(self):
        result = SkillRegistry.names()
        assert isinstance(result, list)


class TestBaseSkill:
    def test_scan_not_implemented(self):
        skill = BaseSkill()
        with pytest.raises(NotImplementedError):
            skill.scan(["us-east-1"])

    def test_remediate_returns_false(self):
        skill = BaseSkill()
        f = Finding(skill="s", title="t", severity=Severity.LOW, description="d")
        assert skill.remediate(f) is False
