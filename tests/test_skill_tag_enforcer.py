"""Tests for Tag Enforcer skill."""
import pytest
from unittest.mock import patch, MagicMock
from ops_agent.skills.tag_enforcer import TagEnforcerSkill, MANDATORY_TAGS
from ops_agent.core import Severity


@pytest.fixture
def skill():
    return TagEnforcerSkill()


class TestTagEnforcerMetadata:
    def test_name(self, skill):
        assert skill.name == "tag-enforcer"

    def test_mandatory_tags(self):
        assert MANDATORY_TAGS == {"Environment", "Team", "Owner"}


class TestEC2Tags:
    @patch("ops_agent.skills.tag_enforcer.get_client")
    def test_finds_untagged_ec2(self, mock_gc):
        ec2_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Reservations": [{"Instances": [
                {"InstanceId": "i-notag", "InstanceType": "t3.micro", "Tags": [{"Key": "Name", "Value": "web"}]},
            ]}]}
        ]
        ec2_mock.get_paginator.return_value = paginator
        mock_gc.return_value = ec2_mock

        skill = TagEnforcerSkill()
        findings = skill._scan_ec2_tags("us-east-1", "test")
        assert len(findings) == 1
        assert "Environment" in findings[0].description or "Team" in findings[0].description

    @patch("ops_agent.skills.tag_enforcer.get_client")
    def test_fully_tagged_ec2_not_flagged(self, mock_gc):
        ec2_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Reservations": [{"Instances": [
                {"InstanceId": "i-tagged", "InstanceType": "t3.micro",
                 "Tags": [{"Key": "Environment", "Value": "prod"}, {"Key": "Team", "Value": "eng"}, {"Key": "Owner", "Value": "alice"}]},
            ]}]}
        ]
        ec2_mock.get_paginator.return_value = paginator
        mock_gc.return_value = ec2_mock

        skill = TagEnforcerSkill()
        findings = skill._scan_ec2_tags("us-east-1", "test")
        assert len(findings) == 0


class TestS3Tags:
    @patch("ops_agent.skills.tag_enforcer.get_client")
    def test_finds_untagged_s3(self, mock_gc):
        s3_mock = MagicMock()
        s3_mock.list_buckets.return_value = {"Buckets": [{"Name": "my-bucket"}]}
        # Simulate no tags
        error = type("ClientError", (Exception,), {})
        s3_mock.exceptions.ClientError = error
        s3_mock.get_bucket_tagging.side_effect = error("NoSuchTagSet")
        mock_gc.return_value = s3_mock

        skill = TagEnforcerSkill()
        findings = skill._scan_s3_tags("test")
        assert len(findings) == 1
        assert "my-bucket" in findings[0].title


class TestLambdaTags:
    @patch("ops_agent.skills.tag_enforcer.get_client")
    def test_finds_untagged_lambda(self, mock_gc):
        lam_mock = MagicMock()
        lam_mock.list_functions.return_value = {
            "Functions": [{"FunctionName": "my-fn", "FunctionArn": "arn:...", "Runtime": "python3.12"}]
        }
        lam_mock.list_tags.return_value = {"Tags": {"Name": "my-fn"}}  # missing mandatory tags
        mock_gc.return_value = lam_mock

        skill = TagEnforcerSkill()
        findings = skill._scan_lambda_tags("us-east-1", "test")
        assert len(findings) == 1


class TestRDSTags:
    @patch("ops_agent.skills.tag_enforcer.get_client")
    def test_finds_untagged_rds(self, mock_gc):
        rds_mock = MagicMock()
        rds_mock.describe_db_instances.return_value = {
            "DBInstances": [{
                "DBInstanceIdentifier": "my-db",
                "DBInstanceArn": "arn:aws:rds:us-east-1:123:db:my-db",
                "DBInstanceClass": "db.t3.micro",
                "Engine": "postgres",
            }]
        }
        rds_mock.list_tags_for_resource.return_value = {"TagList": []}
        mock_gc.return_value = rds_mock

        skill = TagEnforcerSkill()
        findings = skill._scan_rds_tags("us-east-1", "test")
        assert len(findings) == 1
