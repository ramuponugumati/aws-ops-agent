"""Tests for Lifecycle Tracker skill."""
import pytest
from unittest.mock import patch, MagicMock
from ops_agent.skills.lifecycle_tracker import LifecycleTrackerSkill
from ops_agent.core import Severity


@pytest.fixture
def skill():
    return LifecycleTrackerSkill()


class TestLifecycleTrackerMetadata:
    def test_name(self, skill):
        assert skill.name == "lifecycle-tracker"


class TestLambdaRuntimes:
    @patch("ops_agent.skills.lifecycle_tracker.get_client")
    def test_finds_deprecated_python37(self, mock_gc):
        lam_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Functions": [
                {"FunctionName": "old-fn", "Runtime": "python3.7", "FunctionArn": "arn:aws:lambda:us-east-1:123:function:old-fn"},
            ]}
        ]
        lam_mock.get_paginator.return_value = paginator
        mock_gc.return_value = lam_mock

        skill = LifecycleTrackerSkill()
        findings = skill._check_lambda_runtimes("us-east-1", "test")
        assert len(findings) == 1
        assert findings[0].severity == Severity.CRITICAL
        assert "python3.12" in findings[0].description

    @patch("ops_agent.skills.lifecycle_tracker.get_client")
    def test_current_runtime_not_flagged(self, mock_gc):
        lam_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Functions": [
                {"FunctionName": "modern-fn", "Runtime": "python3.12", "FunctionArn": "arn:..."},
            ]}
        ]
        lam_mock.get_paginator.return_value = paginator
        mock_gc.return_value = lam_mock

        skill = LifecycleTrackerSkill()
        findings = skill._check_lambda_runtimes("us-east-1", "test")
        assert len(findings) == 0

    @patch("ops_agent.skills.lifecycle_tracker.get_client")
    def test_finds_deprecated_nodejs16(self, mock_gc):
        lam_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Functions": [
                {"FunctionName": "node-fn", "Runtime": "nodejs16.x", "FunctionArn": "arn:..."},
            ]}
        ]
        lam_mock.get_paginator.return_value = paginator
        mock_gc.return_value = lam_mock

        skill = LifecycleTrackerSkill()
        findings = skill._check_lambda_runtimes("us-east-1", "test")
        assert len(findings) == 1
        assert findings[0].severity == Severity.CRITICAL


class TestRDSEngines:
    @patch("ops_agent.skills.lifecycle_tracker.get_client")
    def test_finds_eol_mysql57(self, mock_gc):
        rds_mock = MagicMock()
        rds_mock.describe_db_instances.return_value = {
            "DBInstances": [{
                "DBInstanceIdentifier": "old-mysql",
                "Engine": "mysql",
                "EngineVersion": "5.7.44",
            }]
        }
        mock_gc.return_value = rds_mock

        skill = LifecycleTrackerSkill()
        findings = skill._check_rds_engines("us-east-1", "test")
        assert len(findings) == 1
        assert findings[0].severity == Severity.CRITICAL
        assert "8.0" in findings[0].description

    @patch("ops_agent.skills.lifecycle_tracker.get_client")
    def test_current_engine_not_flagged(self, mock_gc):
        rds_mock = MagicMock()
        rds_mock.describe_db_instances.return_value = {
            "DBInstances": [{
                "DBInstanceIdentifier": "modern-pg",
                "Engine": "postgres",
                "EngineVersion": "16.1",
            }]
        }
        mock_gc.return_value = rds_mock

        skill = LifecycleTrackerSkill()
        findings = skill._check_rds_engines("us-east-1", "test")
        assert len(findings) == 0


class TestECSPlatforms:
    @patch("ops_agent.skills.lifecycle_tracker.get_client")
    def test_finds_old_fargate_platform(self, mock_gc):
        ecs_mock = MagicMock()
        ecs_mock.list_clusters.return_value = {"clusterArns": ["arn:aws:ecs:us-east-1:123:cluster/my-cluster"]}
        ecs_mock.list_services.return_value = {"serviceArns": ["arn:aws:ecs:us-east-1:123:service/my-svc"]}
        ecs_mock.describe_services.return_value = {
            "services": [{
                "serviceName": "my-svc",
                "launchType": "FARGATE",
                "platformVersion": "1.3.0",
            }]
        }
        mock_gc.return_value = ecs_mock

        skill = LifecycleTrackerSkill()
        findings = skill._check_ecs_platforms("us-east-1", "test")
        assert len(findings) == 1
        assert findings[0].severity == Severity.LOW

    @patch("ops_agent.skills.lifecycle_tracker.get_client")
    def test_latest_platform_not_flagged(self, mock_gc):
        ecs_mock = MagicMock()
        ecs_mock.list_clusters.return_value = {"clusterArns": ["arn:..."]}
        ecs_mock.list_services.return_value = {"serviceArns": ["arn:..."]}
        ecs_mock.describe_services.return_value = {
            "services": [{"serviceName": "svc", "launchType": "FARGATE", "platformVersion": "LATEST"}]
        }
        mock_gc.return_value = ecs_mock

        skill = LifecycleTrackerSkill()
        findings = skill._check_ecs_platforms("us-east-1", "test")
        assert len(findings) == 0
