"""Tests for Resiliency Gaps skill."""
import pytest
from unittest.mock import patch, MagicMock
from ops_agent.skills.resiliency_gaps import ResiliencyGapsSkill
from ops_agent.core import Severity


@pytest.fixture
def skill():
    return ResiliencyGapsSkill()


class TestResiliencyGapsMetadata:
    def test_name(self, skill):
        assert skill.name == "resiliency-gaps"


class TestReliabilityPillar:
    @patch("ops_agent.skills.resiliency_gaps.get_client")
    def test_single_az_rds(self, mock_gc):
        rds_mock = MagicMock()
        rds_mock.describe_db_instances.return_value = {
            "DBInstances": [{
                "DBInstanceIdentifier": "db-single",
                "DBInstanceStatus": "available",
                "DBInstanceClass": "db.r5.large",
                "Engine": "postgres",
                "MultiAZ": False,
            }]
        }
        mock_gc.return_value = rds_mock

        skill = ResiliencyGapsSkill()
        findings = skill._check_single_az_rds("us-east-1", "test")
        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH
        assert "Single-AZ" in findings[0].title

    @patch("ops_agent.skills.resiliency_gaps.get_client")
    def test_multi_az_rds_not_flagged(self, mock_gc):
        rds_mock = MagicMock()
        rds_mock.describe_db_instances.return_value = {
            "DBInstances": [{
                "DBInstanceIdentifier": "db-multi",
                "DBInstanceStatus": "available",
                "DBInstanceClass": "db.r5.large",
                "Engine": "postgres",
                "MultiAZ": True,
            }]
        }
        mock_gc.return_value = rds_mock

        skill = ResiliencyGapsSkill()
        findings = skill._check_single_az_rds("us-east-1", "test")
        assert len(findings) == 0

    @patch("ops_agent.skills.resiliency_gaps.get_client")
    def test_no_backups(self, mock_gc):
        rds_mock = MagicMock()
        rds_mock.describe_db_instances.return_value = {
            "DBInstances": [{
                "DBInstanceIdentifier": "db-nobackup",
                "BackupRetentionPeriod": 0,
            }]
        }
        mock_gc.return_value = rds_mock

        skill = ResiliencyGapsSkill()
        findings = skill._check_no_backups("us-east-1", "test")
        assert len(findings) == 1
        assert findings[0].severity == Severity.CRITICAL

    @patch("ops_agent.skills.resiliency_gaps.get_client")
    def test_single_az_elb(self, mock_gc):
        elb_mock = MagicMock()
        elb_mock.describe_load_balancers.return_value = {
            "LoadBalancers": [{
                "LoadBalancerName": "single-az-alb",
                "LoadBalancerArn": "arn:aws:elasticloadbalancing:us-east-1:123:loadbalancer/app/single-az-alb/abc",
                "AvailabilityZones": [{"ZoneName": "us-east-1a"}],
            }]
        }
        mock_gc.return_value = elb_mock

        skill = ResiliencyGapsSkill()
        findings = skill._check_single_az_elb("us-east-1", "test")
        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH


class TestSecurityPillar:
    @patch("ops_agent.skills.resiliency_gaps.get_client")
    def test_unencrypted_ebs(self, mock_gc):
        ec2_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Volumes": [
                {"VolumeId": "vol-unenc", "VolumeType": "gp3", "Size": 100, "Encrypted": False, "State": "in-use"},
                {"VolumeId": "vol-enc", "VolumeType": "gp3", "Size": 100, "Encrypted": True, "State": "in-use"},
            ]}
        ]
        ec2_mock.get_paginator.return_value = paginator
        mock_gc.return_value = ec2_mock

        skill = ResiliencyGapsSkill()
        findings = skill._check_unencrypted_ebs("us-east-1", "test")
        assert len(findings) == 1
        assert "vol-unenc" in findings[0].title

    @patch("ops_agent.skills.resiliency_gaps.get_client")
    def test_no_vpc_flow_logs(self, mock_gc):
        ec2_mock = MagicMock()
        ec2_mock.describe_vpcs.return_value = {
            "Vpcs": [{"VpcId": "vpc-nologs"}, {"VpcId": "vpc-haslogs"}]
        }
        ec2_mock.describe_flow_logs.return_value = {
            "FlowLogs": [{"ResourceId": "vpc-haslogs", "ResourceType": "VPC"}]
        }
        mock_gc.return_value = ec2_mock

        skill = ResiliencyGapsSkill()
        findings = skill._check_no_vpc_flow_logs("us-east-1", "test")
        assert len(findings) == 1
        assert "vpc-nologs" in findings[0].title


class TestPerformancePillar:
    @patch("ops_agent.skills.resiliency_gaps.get_client")
    def test_old_gen_instances(self, mock_gc):
        ec2_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Reservations": [{"Instances": [
                {"InstanceId": "i-old", "InstanceType": "m4.large", "Tags": [{"Key": "Name", "Value": "legacy"}]},
                {"InstanceId": "i-new", "InstanceType": "m7g.large", "Tags": []},
            ]}]}
        ]
        ec2_mock.get_paginator.return_value = paginator
        mock_gc.return_value = ec2_mock

        skill = ResiliencyGapsSkill()
        findings = skill._check_old_gen_instances("us-east-1", "test")
        assert len(findings) == 1
        assert "i-old" in findings[0].title


class TestSustainabilityPillar:
    @patch("ops_agent.skills.resiliency_gaps.get_client")
    def test_graviton_eligible(self, mock_gc):
        ec2_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Reservations": [{"Instances": [
                {"InstanceId": "i-x86", "InstanceType": "m5.large", "Tags": [{"Key": "Name", "Value": "web"}]},
            ]}]}
        ]
        ec2_mock.get_paginator.return_value = paginator
        mock_gc.return_value = ec2_mock

        skill = ResiliencyGapsSkill()
        findings = skill._check_graviton_eligible("us-east-1", "test")
        assert len(findings) == 1
        assert "m7g" in findings[0].description
