"""Tests for Security Posture skill."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
from ops_agent.skills.security_posture import SecurityPostureSkill
from ops_agent.core import Severity


@pytest.fixture
def skill():
    return SecurityPostureSkill()


class TestSecurityPostureMetadata:
    def test_name(self, skill):
        assert skill.name == "security-posture"

    def test_version(self, skill):
        assert skill.version == "0.2.0"


class TestGuardDuty:
    @patch("ops_agent.skills.security_posture.get_client")
    def test_finds_guardduty_findings(self, mock_gc):
        gd_mock = MagicMock()
        gd_mock.list_detectors.return_value = {"DetectorIds": ["det-123"]}
        gd_mock.list_findings.return_value = {"FindingIds": ["f-1"]}
        gd_mock.get_findings.return_value = {
            "Findings": [{
                "Title": "Unusual API call",
                "Severity": 8.5,
                "Description": "Suspicious activity detected",
                "Type": "Recon:EC2/PortProbeUnprotectedPort",
                "Resource": {"ResourceType": "Instance"},
            }]
        }
        mock_gc.return_value = gd_mock

        skill = SecurityPostureSkill()
        findings = skill._check_guardduty("us-east-1", "test")
        assert len(findings) == 1
        assert findings[0].severity == Severity.CRITICAL  # severity >= 8

    @patch("ops_agent.skills.security_posture.get_client")
    def test_no_detectors(self, mock_gc):
        gd_mock = MagicMock()
        gd_mock.list_detectors.return_value = {"DetectorIds": []}
        mock_gc.return_value = gd_mock

        skill = SecurityPostureSkill()
        findings = skill._check_guardduty("us-east-1", "test")
        assert len(findings) == 0

    @patch("ops_agent.skills.security_posture.get_client")
    def test_severity_mapping(self, mock_gc):
        gd_mock = MagicMock()
        gd_mock.list_detectors.return_value = {"DetectorIds": ["det-1"]}
        gd_mock.list_findings.return_value = {"FindingIds": ["f-1", "f-2", "f-3"]}
        gd_mock.get_findings.return_value = {
            "Findings": [
                {"Title": "Critical", "Severity": 9.0, "Description": "", "Type": "t", "Resource": {"ResourceType": ""}},
                {"Title": "High", "Severity": 6.0, "Description": "", "Type": "t", "Resource": {"ResourceType": ""}},
                {"Title": "Medium", "Severity": 4.0, "Description": "", "Type": "t", "Resource": {"ResourceType": ""}},
            ]
        }
        mock_gc.return_value = gd_mock

        skill = SecurityPostureSkill()
        findings = skill._check_guardduty("us-east-1", "test")
        assert findings[0].severity == Severity.CRITICAL
        assert findings[1].severity == Severity.HIGH
        assert findings[2].severity == Severity.MEDIUM


class TestPublicS3:
    @patch("ops_agent.skills.security_posture.get_client")
    def test_finds_public_buckets(self, mock_gc):
        s3_mock = MagicMock()
        s3_mock.list_buckets.return_value = {"Buckets": [{"Name": "public-bucket"}]}
        s3_mock.get_bucket_acl.return_value = {
            "Grants": [{"Grantee": {"URI": "http://acs.amazonaws.com/groups/global/AllUsers"}, "Permission": "READ"}]
        }
        mock_gc.return_value = s3_mock

        skill = SecurityPostureSkill()
        findings = skill._check_public_s3("test")
        assert len(findings) == 1
        assert findings[0].severity == Severity.CRITICAL
        assert "public-bucket" in findings[0].title

    @patch("ops_agent.skills.security_posture.get_client")
    def test_private_bucket_not_flagged(self, mock_gc):
        s3_mock = MagicMock()
        s3_mock.list_buckets.return_value = {"Buckets": [{"Name": "private-bucket"}]}
        s3_mock.get_bucket_acl.return_value = {
            "Grants": [{"Grantee": {"Type": "CanonicalUser", "ID": "abc123"}, "Permission": "FULL_CONTROL"}]
        }
        mock_gc.return_value = s3_mock

        skill = SecurityPostureSkill()
        findings = skill._check_public_s3("test")
        assert len(findings) == 0


class TestOpenSecurityGroups:
    @patch("ops_agent.skills.security_posture.get_client")
    def test_finds_open_ssh(self, mock_gc):
        ec2_mock = MagicMock()
        ec2_mock.describe_security_groups.return_value = {
            "SecurityGroups": [{
                "GroupId": "sg-open22",
                "GroupName": "default",
                "IpPermissions": [{"FromPort": 22, "ToPort": 22, "IpProtocol": "tcp",
                                   "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
            }]
        }
        mock_gc.return_value = ec2_mock

        skill = SecurityPostureSkill()
        findings = skill._check_open_sgs("us-east-1", "test")
        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH
        assert "port 22" in findings[0].title

    @patch("ops_agent.skills.security_posture.get_client")
    def test_finds_open_rdp(self, mock_gc):
        ec2_mock = MagicMock()
        ec2_mock.describe_security_groups.return_value = {
            "SecurityGroups": [{
                "GroupId": "sg-open3389",
                "GroupName": "windows",
                "IpPermissions": [{"FromPort": 3389, "ToPort": 3389, "IpProtocol": "tcp",
                                   "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
            }]
        }
        mock_gc.return_value = ec2_mock

        skill = SecurityPostureSkill()
        findings = skill._check_open_sgs("us-east-1", "test")
        assert len(findings) == 1
        assert "port 3389" in findings[0].title

    @patch("ops_agent.skills.security_posture.get_client")
    def test_safe_port_not_flagged(self, mock_gc):
        ec2_mock = MagicMock()
        ec2_mock.describe_security_groups.return_value = {
            "SecurityGroups": [{
                "GroupId": "sg-http",
                "GroupName": "web",
                "IpPermissions": [{"FromPort": 443, "ToPort": 443, "IpProtocol": "tcp",
                                   "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}],
            }]
        }
        mock_gc.return_value = ec2_mock

        skill = SecurityPostureSkill()
        findings = skill._check_open_sgs("us-east-1", "test")
        assert len(findings) == 0


class TestOldAccessKeys:
    @patch("ops_agent.skills.security_posture.get_client")
    def test_finds_old_keys(self, mock_gc):
        iam_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Users": [{"UserName": "old-user"}]}
        ]
        iam_mock.get_paginator.return_value = paginator
        iam_mock.list_access_keys.return_value = {
            "AccessKeyMetadata": [{
                "AccessKeyId": "AKIA_OLD",
                "Status": "Active",
                "CreateDate": datetime.now(timezone.utc) - timedelta(days=120),
            }]
        }
        mock_gc.return_value = iam_mock

        skill = SecurityPostureSkill()
        findings = skill._check_old_access_keys("test", max_age_days=90)
        assert len(findings) == 1
        assert findings[0].severity == Severity.MEDIUM
        assert "old-user" in findings[0].title

    @patch("ops_agent.skills.security_posture.get_client")
    def test_new_key_not_flagged(self, mock_gc):
        iam_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Users": [{"UserName": "new-user"}]}
        ]
        iam_mock.get_paginator.return_value = paginator
        iam_mock.list_access_keys.return_value = {
            "AccessKeyMetadata": [{
                "AccessKeyId": "AKIA_NEW",
                "Status": "Active",
                "CreateDate": datetime.now(timezone.utc) - timedelta(days=10),
            }]
        }
        mock_gc.return_value = iam_mock

        skill = SecurityPostureSkill()
        findings = skill._check_old_access_keys("test", max_age_days=90)
        assert len(findings) == 0


class TestSecurityHub:
    @patch("ops_agent.skills.security_posture.get_client")
    def test_finds_failed_controls(self, mock_gc):
        sh_mock = MagicMock()
        sh_mock.get_findings.return_value = {
            "Findings": [{
                "Compliance": {"SecurityControlId": "CIS.1.4"},
                "Severity": {"Label": "CRITICAL"},
                "Title": "Ensure MFA is enabled for root",
                "Resources": [{"Id": "arn:aws:iam::root"}],
                "GeneratorId": "gen/CIS.1.4",
            }]
        }
        mock_gc.return_value = sh_mock

        skill = SecurityPostureSkill()
        findings = skill._check_security_hub("us-east-1", "test")
        assert len(findings) == 1
        assert findings[0].severity == Severity.CRITICAL
        assert "CIS.1.4" in findings[0].title
