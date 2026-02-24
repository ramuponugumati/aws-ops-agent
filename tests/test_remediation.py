"""Tests for remediation engine."""
import pytest
from unittest.mock import patch, MagicMock
from ops_agent.dashboard.remediation import (
    has_remediation, execute_remediation, RemediationResult,
    REMEDIATION_PATTERNS,
)


class TestHasRemediation:
    def test_ebs_has_remediation(self):
        f = {"skill": "zombie-hunter", "title": "Unattached EBS: vol-abc"}
        assert has_remediation(f) is True

    def test_eip_has_remediation(self):
        f = {"skill": "zombie-hunter", "title": "Unused EIP: 1.2.3.4"}
        assert has_remediation(f) is True

    def test_open_port_has_remediation(self):
        f = {"skill": "security-posture", "title": "Open port 22 to 0.0.0.0/0: sg-abc"}
        assert has_remediation(f) is True

    def test_public_s3_has_remediation(self):
        f = {"skill": "security-posture", "title": "Public S3 bucket: my-bucket"}
        assert has_remediation(f) is True

    def test_old_key_has_remediation(self):
        f = {"skill": "security-posture", "title": "Old access key: user1 (120 days)"}
        assert has_remediation(f) is True

    def test_single_az_rds_has_remediation(self):
        f = {"skill": "resiliency-gaps", "title": "Single-AZ RDS: my-db"}
        assert has_remediation(f) is True

    def test_untagged_ec2_has_remediation(self):
        f = {"skill": "tag-enforcer", "title": "Untagged EC2: i-123"}
        assert has_remediation(f) is True

    def test_unknown_finding_no_remediation(self):
        f = {"skill": "cost-anomaly", "title": "Cost anomaly: $500 impact"}
        assert has_remediation(f) is False

    # --- Missing has_remediation checks ---

    def test_nat_gw_has_remediation(self):
        f = {"skill": "zombie-hunter", "title": "Unused NAT GW: nat-abc"}
        assert has_remediation(f) is True

    def test_idle_ec2_has_remediation(self):
        f = {"skill": "zombie-hunter", "title": "Idle EC2: i-abc"}
        assert has_remediation(f) is True

    def test_idle_rds_has_remediation(self):
        f = {"skill": "zombie-hunter", "title": "Idle RDS: my-db"}
        assert has_remediation(f) is True

    def test_no_backups_rds_has_remediation(self):
        f = {"skill": "resiliency-gaps", "title": "No backups: RDS my-db"}
        assert has_remediation(f) is True

    def test_no_vpc_flow_logs_has_remediation(self):
        f = {"skill": "resiliency-gaps", "title": "No VPC Flow Logs: vpc-abc"}
        assert has_remediation(f) is True

    def test_underutilized_odcr_has_remediation(self):
        f = {"skill": "capacity-planner", "title": "Underutilized ODCR: cr-abc"}
        assert has_remediation(f) is True

    def test_untagged_rds_has_remediation(self):
        f = {"skill": "tag-enforcer", "title": "Untagged RDS: my-db"}
        assert has_remediation(f) is True

    def test_untagged_s3_has_remediation(self):
        f = {"skill": "tag-enforcer", "title": "Untagged S3: my-bucket"}
        assert has_remediation(f) is True

    def test_untagged_lambda_has_remediation(self):
        f = {"skill": "tag-enforcer", "title": "Untagged Lambda: my-fn"}
        assert has_remediation(f) is True

    def test_deprecated_runtime_has_remediation(self):
        f = {"skill": "lifecycle-tracker", "title": "Deprecated runtime: old-fn"}
        assert has_remediation(f) is True

    def test_eol_rds_engine_has_remediation(self):
        f = {"skill": "lifecycle-tracker", "title": "EOL RDS engine: old-db"}
        assert has_remediation(f) is True

    def test_empty_finding(self):
        assert has_remediation({}) is False

    def test_all_patterns_covered(self):
        """Verify every pattern in REMEDIATION_PATTERNS has a handler."""
        from ops_agent.dashboard.remediation import _HANDLERS
        for skill, pattern, action in REMEDIATION_PATTERNS:
            assert action in _HANDLERS, f"Missing handler for {action}"


class TestExecuteRemediation:
    @patch("ops_agent.dashboard.remediation.get_client")
    def test_delete_ebs_volume(self, mock_gc):
        ec2_mock = MagicMock()
        mock_gc.return_value = ec2_mock

        finding = {
            "skill": "zombie-hunter",
            "title": "Unattached EBS: vol-abc123",
            "resource_id": "vol-abc123",
            "region": "us-east-1",
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        assert "vol-abc123" in result.message
        ec2_mock.delete_volume.assert_called_once_with(VolumeId="vol-abc123")

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_release_eip(self, mock_gc):
        ec2_mock = MagicMock()
        mock_gc.return_value = ec2_mock

        finding = {
            "skill": "zombie-hunter",
            "title": "Unused EIP: 1.2.3.4",
            "resource_id": "eipalloc-abc",
            "region": "us-east-1",
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        ec2_mock.release_address.assert_called_once_with(AllocationId="eipalloc-abc")

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_restrict_security_group(self, mock_gc):
        ec2_mock = MagicMock()
        mock_gc.return_value = ec2_mock

        finding = {
            "skill": "security-posture",
            "title": "Open port 22 to 0.0.0.0/0: sg-xyz",
            "resource_id": "sg-xyz",
            "region": "us-east-1",
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        ec2_mock.revoke_security_group_ingress.assert_called_once()
        call_kwargs = ec2_mock.revoke_security_group_ingress.call_args[1]
        assert call_kwargs["GroupId"] == "sg-xyz"
        assert call_kwargs["IpPermissions"][0]["FromPort"] == 22

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_block_s3_public_access(self, mock_gc):
        s3_mock = MagicMock()
        mock_gc.return_value = s3_mock

        finding = {
            "skill": "security-posture",
            "title": "Public S3 bucket: my-bucket",
            "resource_id": "my-bucket",
            "region": "us-east-1",
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        s3_mock.put_public_access_block.assert_called_once()

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_deactivate_access_key(self, mock_gc):
        iam_mock = MagicMock()
        mock_gc.return_value = iam_mock

        finding = {
            "skill": "security-posture",
            "title": "Old access key: admin-user (120 days)",
            "resource_id": "AKIA_OLD",
            "region": "us-east-1",
            "metadata": {"user": "admin-user"},
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        iam_mock.update_access_key.assert_called_once_with(
            UserName="admin-user", AccessKeyId="AKIA_OLD", Status="Inactive"
        )

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_stop_ec2_instance(self, mock_gc):
        ec2_mock = MagicMock()
        mock_gc.return_value = ec2_mock

        finding = {
            "skill": "zombie-hunter",
            "title": "Idle EC2: i-idle001",
            "resource_id": "i-idle001",
            "region": "us-west-2",
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        ec2_mock.stop_instances.assert_called_once_with(InstanceIds=["i-idle001"])

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_enable_rds_multi_az(self, mock_gc):
        rds_mock = MagicMock()
        mock_gc.return_value = rds_mock

        finding = {
            "skill": "resiliency-gaps",
            "title": "Single-AZ RDS: my-db",
            "resource_id": "my-db",
            "region": "us-east-1",
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        rds_mock.modify_db_instance.assert_called_once()

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_apply_tags_ec2(self, mock_gc):
        ec2_mock = MagicMock()
        mock_gc.return_value = ec2_mock

        finding = {
            "skill": "tag-enforcer",
            "title": "Untagged EC2: i-notag",
            "resource_id": "i-notag",
            "region": "us-east-1",
            "metadata": {"missing_tags": ["Environment", "Team"]},
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        ec2_mock.create_tags.assert_called_once()

    # --- The 10 missing handlers ---

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_delete_nat_gateway(self, mock_gc):
        ec2_mock = MagicMock()
        mock_gc.return_value = ec2_mock

        finding = {
            "skill": "zombie-hunter",
            "title": "Unused NAT GW: nat-abc123",
            "resource_id": "nat-abc123",
            "region": "us-east-1",
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        assert "nat-abc123" in result.message
        ec2_mock.delete_nat_gateway.assert_called_once_with(NatGatewayId="nat-abc123")

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_stop_rds_instance(self, mock_gc):
        rds_mock = MagicMock()
        mock_gc.return_value = rds_mock

        finding = {
            "skill": "zombie-hunter",
            "title": "Idle RDS: my-idle-db",
            "resource_id": "my-idle-db",
            "region": "us-west-2",
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        rds_mock.stop_db_instance.assert_called_once_with(DBInstanceIdentifier="my-idle-db")

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_enable_rds_backups(self, mock_gc):
        rds_mock = MagicMock()
        mock_gc.return_value = rds_mock

        finding = {
            "skill": "resiliency-gaps",
            "title": "No backups: RDS db-nobackup",
            "resource_id": "db-nobackup",
            "region": "us-east-1",
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        rds_mock.modify_db_instance.assert_called_once_with(
            DBInstanceIdentifier="db-nobackup",
            BackupRetentionPeriod=7,
            ApplyImmediately=True,
        )

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_enable_vpc_flow_logs(self, mock_gc):
        ec2_mock = MagicMock()
        mock_gc.return_value = ec2_mock

        finding = {
            "skill": "resiliency-gaps",
            "title": "No VPC Flow Logs: vpc-abc123",
            "resource_id": "vpc-abc123",
            "region": "us-east-1",
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        ec2_mock.create_flow_logs.assert_called_once()
        call_kwargs = ec2_mock.create_flow_logs.call_args[1]
        assert call_kwargs["ResourceIds"] == ["vpc-abc123"]
        assert call_kwargs["ResourceType"] == "VPC"
        assert call_kwargs["TrafficType"] == "ALL"

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_cancel_capacity_reservation(self, mock_gc):
        ec2_mock = MagicMock()
        mock_gc.return_value = ec2_mock

        finding = {
            "skill": "capacity-planner",
            "title": "Underutilized ODCR: cr-abc123",
            "resource_id": "cr-abc123",
            "region": "us-east-1",
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        ec2_mock.cancel_capacity_reservation.assert_called_once_with(CapacityReservationId="cr-abc123")

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_apply_tags_rds(self, mock_gc):
        rds_mock = MagicMock()
        rds_mock.describe_db_instances.return_value = {
            "DBInstances": [{"DBInstanceArn": "arn:aws:rds:us-east-1:123:db:my-db"}]
        }
        mock_gc.return_value = rds_mock

        finding = {
            "skill": "tag-enforcer",
            "title": "Untagged RDS: my-db",
            "resource_id": "my-db",
            "region": "us-east-1",
            "metadata": {"missing_tags": ["Environment", "Owner"], "arn": "arn:aws:rds:us-east-1:123:db:my-db"},
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        rds_mock.add_tags_to_resource.assert_called_once()
        call_kwargs = rds_mock.add_tags_to_resource.call_args[1]
        assert call_kwargs["ResourceName"] == "arn:aws:rds:us-east-1:123:db:my-db"
        tag_keys = [t["Key"] for t in call_kwargs["Tags"]]
        assert "Environment" in tag_keys
        assert "Owner" in tag_keys

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_apply_tags_s3(self, mock_gc):
        s3_mock = MagicMock()
        s3_mock.get_bucket_tagging.return_value = {"TagSet": [{"Key": "Existing", "Value": "tag"}]}
        mock_gc.return_value = s3_mock

        finding = {
            "skill": "tag-enforcer",
            "title": "Untagged S3: my-bucket",
            "resource_id": "my-bucket",
            "region": "us-east-1",
            "metadata": {"missing_tags": ["Environment", "Team"]},
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        s3_mock.put_bucket_tagging.assert_called_once()
        call_kwargs = s3_mock.put_bucket_tagging.call_args[1]
        tag_keys = [t["Key"] for t in call_kwargs["Tagging"]["TagSet"]]
        assert "Existing" in tag_keys  # preserved existing
        assert "Environment" in tag_keys
        assert "Team" in tag_keys

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_apply_tags_s3_no_existing_tags(self, mock_gc):
        s3_mock = MagicMock()
        s3_mock.get_bucket_tagging.side_effect = Exception("NoSuchTagSet")
        mock_gc.return_value = s3_mock

        finding = {
            "skill": "tag-enforcer",
            "title": "Untagged S3: empty-bucket",
            "resource_id": "empty-bucket",
            "region": "us-east-1",
            "metadata": {"missing_tags": ["Owner"]},
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        s3_mock.put_bucket_tagging.assert_called_once()

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_apply_tags_lambda(self, mock_gc):
        lam_mock = MagicMock()
        lam_mock.get_function.return_value = {
            "Configuration": {"FunctionArn": "arn:aws:lambda:us-east-1:123:function:my-fn"}
        }
        mock_gc.return_value = lam_mock

        finding = {
            "skill": "tag-enforcer",
            "title": "Untagged Lambda: my-fn",
            "resource_id": "my-fn",
            "region": "us-east-1",
            "metadata": {"missing_tags": ["Environment", "Team", "Owner"], "arn": "arn:aws:lambda:us-east-1:123:function:my-fn"},
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        lam_mock.tag_resource.assert_called_once()
        call_kwargs = lam_mock.tag_resource.call_args[1]
        assert call_kwargs["Resource"] == "arn:aws:lambda:us-east-1:123:function:my-fn"
        assert "Environment" in call_kwargs["Tags"]

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_upgrade_lambda_runtime(self, mock_gc):
        lam_mock = MagicMock()
        mock_gc.return_value = lam_mock

        finding = {
            "skill": "lifecycle-tracker",
            "title": "Deprecated runtime: old-fn",
            "resource_id": "old-fn",
            "region": "us-east-1",
            "metadata": {"upgrade_to": "python3.12", "arn": "arn:aws:lambda:us-east-1:123:function:old-fn"},
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        lam_mock.update_function_configuration.assert_called_once_with(
            FunctionName="arn:aws:lambda:us-east-1:123:function:old-fn",
            Runtime="python3.12",
        )

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_upgrade_rds_engine(self, mock_gc):
        rds_mock = MagicMock()
        mock_gc.return_value = rds_mock

        finding = {
            "skill": "lifecycle-tracker",
            "title": "EOL RDS engine: old-mysql-db",
            "resource_id": "old-mysql-db",
            "region": "us-east-1",
            "metadata": {"engine": "mysql", "version": "5.7.44", "upgrade_to": "8.0"},
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        rds_mock.modify_db_instance.assert_called_once()
        call_kwargs = rds_mock.modify_db_instance.call_args[1]
        assert call_kwargs["DBInstanceIdentifier"] == "old-mysql-db"
        assert call_kwargs["EngineVersion"] == "8.0"
        assert call_kwargs["AllowMajorVersionUpgrade"] is True

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_upgrade_rds_engine_no_version_fails(self, mock_gc):
        rds_mock = MagicMock()
        mock_gc.return_value = rds_mock

        finding = {
            "skill": "lifecycle-tracker",
            "title": "EOL RDS engine: bad-db",
            "resource_id": "bad-db",
            "region": "us-east-1",
            "metadata": {"engine": "mysql", "version": "5.7"},  # no upgrade_to
        }
        result = execute_remediation(finding, "test")
        assert result.success is False
        assert "No upgrade version" in result.message

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_deactivate_key_extracts_user_from_title(self, mock_gc):
        """Test fallback: extract username from title when metadata.user is missing."""
        iam_mock = MagicMock()
        mock_gc.return_value = iam_mock

        finding = {
            "skill": "security-posture",
            "title": "Old access key: deploy-bot (200 days)",
            "resource_id": "AKIA_DEPLOY",
            "region": "us-east-1",
            "metadata": {},  # no user key
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        iam_mock.update_access_key.assert_called_once_with(
            UserName="deploy-bot", AccessKeyId="AKIA_DEPLOY", Status="Inactive"
        )

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_restrict_sg_port_3389(self, mock_gc):
        """Test SG restriction works for RDP port too."""
        ec2_mock = MagicMock()
        mock_gc.return_value = ec2_mock

        finding = {
            "skill": "security-posture",
            "title": "Open port 3389 to 0.0.0.0/0: sg-rdp",
            "resource_id": "sg-rdp",
            "region": "us-east-1",
        }
        result = execute_remediation(finding, "test")
        assert result.success is True
        call_kwargs = ec2_mock.revoke_security_group_ingress.call_args[1]
        assert call_kwargs["IpPermissions"][0]["FromPort"] == 3389

    @patch("ops_agent.dashboard.remediation.get_client")
    def test_remediation_failure(self, mock_gc):
        ec2_mock = MagicMock()
        ec2_mock.delete_volume.side_effect = Exception("Access denied")
        mock_gc.return_value = ec2_mock

        finding = {
            "skill": "zombie-hunter",
            "title": "Unattached EBS: vol-fail",
            "resource_id": "vol-fail",
            "region": "us-east-1",
        }
        result = execute_remediation(finding, "test")
        assert result.success is False
        assert "Access denied" in result.message

    def test_no_handler_available(self):
        finding = {"skill": "unknown", "title": "Unknown finding", "resource_id": "x"}
        result = execute_remediation(finding, "test")
        assert result.success is False
        assert result.action == "none"
