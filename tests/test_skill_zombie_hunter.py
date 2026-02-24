"""Tests for Zombie Hunter skill."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from ops_agent.skills.zombie_hunter import ZombieHunterSkill
from ops_agent.core import Severity


@pytest.fixture
def skill():
    return ZombieHunterSkill()


class TestZombieHunterMetadata:
    def test_name(self, skill):
        assert skill.name == "zombie-hunter"

    def test_version(self, skill):
        assert skill.version == "0.1.0"


class TestScanEBS:
    @patch("ops_agent.skills.zombie_hunter.get_account_id", return_value="123456789012")
    @patch("ops_agent.skills.zombie_hunter.get_client")
    def test_finds_unattached_volumes(self, mock_gc, mock_aid):
        ec2_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Volumes": [
                {"VolumeId": "vol-aaa", "VolumeType": "gp2", "Size": 100, "State": "available"},
                {"VolumeId": "vol-bbb", "VolumeType": "gp3", "Size": 50, "State": "available"},
            ]}
        ]
        ec2_mock.get_paginator.return_value = paginator
        mock_gc.return_value = ec2_mock

        skill = ZombieHunterSkill()
        findings = skill._scan_ebs("us-east-1", "test")
        assert len(findings) == 2
        assert findings[0].title == "Unattached EBS: vol-aaa"
        assert findings[0].severity == Severity.LOW
        assert findings[0].monthly_impact == 8.0  # 100 * 0.08
        assert findings[1].monthly_impact == 4.0  # 50 * 0.08

    @patch("ops_agent.skills.zombie_hunter.get_client")
    def test_no_unattached_volumes(self, mock_gc):
        ec2_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [{"Volumes": []}]
        ec2_mock.get_paginator.return_value = paginator
        mock_gc.return_value = ec2_mock

        skill = ZombieHunterSkill()
        findings = skill._scan_ebs("us-east-1", "test")
        assert len(findings) == 0


class TestScanEIP:
    @patch("ops_agent.skills.zombie_hunter.get_client")
    def test_finds_unused_eips(self, mock_gc):
        ec2_mock = MagicMock()
        ec2_mock.describe_addresses.return_value = {
            "Addresses": [
                {"PublicIp": "1.2.3.4", "AllocationId": "eipalloc-aaa"},  # unused
                {"PublicIp": "5.6.7.8", "AllocationId": "eipalloc-bbb", "InstanceId": "i-123"},  # in use
            ]
        }
        mock_gc.return_value = ec2_mock

        skill = ZombieHunterSkill()
        findings = skill._scan_eip("us-east-1", "test")
        assert len(findings) == 1
        assert "1.2.3.4" in findings[0].title
        assert findings[0].monthly_impact == 3.60


class TestScanNAT:
    @patch("ops_agent.skills.zombie_hunter.get_client")
    def test_finds_unused_nat(self, mock_gc):
        ec2_mock = MagicMock()
        ec2_mock.describe_nat_gateways.return_value = {
            "NatGateways": [{"NatGatewayId": "nat-aaa", "VpcId": "vpc-123"}]
        }
        cw_mock = MagicMock()
        cw_mock.get_metric_statistics.return_value = {"Datapoints": [{"Sum": 0}]}

        def side_effect(service, region, profile):
            if service == "ec2":
                return ec2_mock
            return cw_mock
        mock_gc.side_effect = side_effect

        skill = ZombieHunterSkill()
        findings = skill._scan_nat("us-east-1", "test")
        assert len(findings) == 1
        assert findings[0].severity == Severity.MEDIUM
        assert findings[0].monthly_impact == 32.85

    @patch("ops_agent.skills.zombie_hunter.get_client")
    def test_active_nat_not_flagged(self, mock_gc):
        ec2_mock = MagicMock()
        ec2_mock.describe_nat_gateways.return_value = {
            "NatGateways": [{"NatGatewayId": "nat-bbb", "VpcId": "vpc-456"}]
        }
        cw_mock = MagicMock()
        cw_mock.get_metric_statistics.return_value = {"Datapoints": [{"Sum": 1000000}]}

        def side_effect(service, region, profile):
            if service == "ec2":
                return ec2_mock
            return cw_mock
        mock_gc.side_effect = side_effect

        skill = ZombieHunterSkill()
        findings = skill._scan_nat("us-east-1", "test")
        assert len(findings) == 0


class TestScanIdleEC2:
    @patch("ops_agent.skills.zombie_hunter.get_client")
    def test_finds_idle_instances(self, mock_gc):
        ec2_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Reservations": [{"Instances": [
                {"InstanceId": "i-idle1", "InstanceType": "t3.large"},
            ]}]}
        ]
        ec2_mock.get_paginator.return_value = paginator

        cw_mock = MagicMock()
        cw_mock.get_metric_statistics.return_value = {
            "Datapoints": [{"Average": 0.5}, {"Average": 0.3}]
        }

        def side_effect(service, region, profile):
            if service == "ec2":
                return ec2_mock
            return cw_mock
        mock_gc.side_effect = side_effect

        skill = ZombieHunterSkill()
        findings = skill._scan_idle_ec2("us-east-1", "test", 2.0)
        assert len(findings) == 1
        assert "Idle EC2" in findings[0].title
        assert findings[0].severity == Severity.MEDIUM

    @patch("ops_agent.skills.zombie_hunter.get_client")
    def test_active_instance_not_flagged(self, mock_gc):
        ec2_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Reservations": [{"Instances": [
                {"InstanceId": "i-active1", "InstanceType": "m5.xlarge"},
            ]}]}
        ]
        ec2_mock.get_paginator.return_value = paginator

        cw_mock = MagicMock()
        cw_mock.get_metric_statistics.return_value = {
            "Datapoints": [{"Average": 45.0}, {"Average": 50.0}]
        }

        def side_effect(service, region, profile):
            if service == "ec2":
                return ec2_mock
            return cw_mock
        mock_gc.side_effect = side_effect

        skill = ZombieHunterSkill()
        findings = skill._scan_idle_ec2("us-east-1", "test", 2.0)
        assert len(findings) == 0


class TestScanIdleRDS:
    @patch("ops_agent.skills.zombie_hunter.get_client")
    def test_finds_idle_rds(self, mock_gc):
        rds_mock = MagicMock()
        rds_mock.describe_db_instances.return_value = {
            "DBInstances": [
                {"DBInstanceIdentifier": "db-idle", "DBInstanceStatus": "available",
                 "DBInstanceClass": "db.r5.large", "Engine": "postgres"}
            ]
        }
        cw_mock = MagicMock()
        cw_mock.get_metric_statistics.return_value = {
            "Datapoints": [{"Average": 0.0}]
        }

        def side_effect(service, region, profile):
            if service == "rds":
                return rds_mock
            return cw_mock
        mock_gc.side_effect = side_effect

        skill = ZombieHunterSkill()
        findings = skill._scan_idle_rds("us-east-1", "test")
        assert len(findings) == 1
        assert "Idle RDS" in findings[0].title
