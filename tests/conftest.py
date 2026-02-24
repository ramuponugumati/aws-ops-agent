"""Shared fixtures for all tests."""
import pytest
from unittest.mock import MagicMock, patch
from ops_agent.core import Finding, Severity, SkillResult, SkillRegistry, BaseSkill


@pytest.fixture
def mock_profile():
    return "test-profile"


@pytest.fixture
def mock_regions():
    return ["us-east-1", "us-west-2"]


@pytest.fixture
def mock_account_id():
    return "123456789012"


@pytest.fixture(autouse=True)
def patch_get_account_id(mock_account_id):
    """Patch get_account_id globally so no test hits real STS."""
    with patch("ops_agent.aws_client.get_client") as mock_gc:
        sts_mock = MagicMock()
        sts_mock.get_caller_identity.return_value = {"Account": mock_account_id}
        mock_gc.return_value = sts_mock
        yield mock_gc


@pytest.fixture
def sample_finding():
    return Finding(
        skill="test-skill",
        title="Test finding",
        severity=Severity.HIGH,
        description="A test finding",
        resource_id="i-1234567890abcdef0",
        account_id="123456789012",
        region="us-east-1",
        monthly_impact=100.0,
        recommended_action="Fix it",
        metadata={"key": "value"},
    )


@pytest.fixture
def sample_skill_result(sample_finding):
    return SkillResult(
        skill_name="test-skill",
        findings=[sample_finding],
        duration_seconds=1.5,
        accounts_scanned=1,
        regions_scanned=2,
    )


@pytest.fixture
def sample_findings_list():
    """A realistic set of findings across skills for chat/dashboard tests."""
    return [
        Finding(
            skill="zombie-hunter", title="Unattached EBS: vol-abc123",
            severity=Severity.LOW, description="gp2 | 100GB",
            resource_id="vol-abc123", region="us-east-1",
            monthly_impact=8.0, recommended_action="Delete or snapshot+delete",
        ).to_dict(),
        Finding(
            skill="security-posture", title="Open port 22 to 0.0.0.0/0: sg-xyz789",
            severity=Severity.HIGH, description="SG 'default' allows inbound on port 22",
            resource_id="sg-xyz789", region="us-east-1",
            monthly_impact=0, recommended_action="Restrict source IP range",
        ).to_dict(),
        Finding(
            skill="zombie-hunter", title="Idle EC2: i-idle001",
            severity=Severity.MEDIUM, description="t3.large | CPU: 0.5%",
            resource_id="i-idle001", region="us-west-2",
            monthly_impact=73.0, recommended_action="Stop or terminate",
        ).to_dict(),
    ]
