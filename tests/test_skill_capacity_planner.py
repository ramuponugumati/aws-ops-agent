"""Tests for Capacity Planner skill."""
import pytest
from unittest.mock import patch, MagicMock
from ops_agent.skills.capacity_planner import CapacityPlannerSkill
from ops_agent.core import Severity


@pytest.fixture
def skill():
    return CapacityPlannerSkill()


class TestCapacityPlannerMetadata:
    def test_name(self, skill):
        assert skill.name == "capacity-planner"


class TestODCRUtilization:
    @patch("ops_agent.skills.capacity_planner.get_client")
    def test_finds_underutilized_odcr(self, mock_gc):
        ec2_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"CapacityReservations": [{
                "CapacityReservationId": "cr-under",
                "InstanceType": "m5.xlarge",
                "TotalInstanceCount": 10,
                "AvailableInstanceCount": 8,  # 80% idle
            }]}
        ]
        ec2_mock.get_paginator.return_value = paginator
        mock_gc.return_value = ec2_mock

        skill = CapacityPlannerSkill()
        findings = skill._check_odcr_utilization("us-east-1", "test")
        assert len(findings) == 1
        assert findings[0].severity == Severity.MEDIUM
        assert findings[0].monthly_impact > 0

    @patch("ops_agent.skills.capacity_planner.get_client")
    def test_fully_utilized_odcr(self, mock_gc):
        ec2_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"CapacityReservations": [{
                "CapacityReservationId": "cr-full",
                "InstanceType": "m5.xlarge",
                "TotalInstanceCount": 5,
                "AvailableInstanceCount": 0,
            }]}
        ]
        ec2_mock.get_paginator.return_value = paginator
        mock_gc.return_value = ec2_mock

        skill = CapacityPlannerSkill()
        findings = skill._check_odcr_utilization("us-east-1", "test")
        assert len(findings) == 1
        assert "fully utilized" in findings[0].title


class TestSageMakerCapacity:
    @patch("ops_agent.skills.capacity_planner.get_client")
    def test_finds_at_max_capacity(self, mock_gc):
        sm_mock = MagicMock()
        sm_mock.list_endpoints.return_value = {
            "Endpoints": [{"EndpointName": "my-endpoint"}]
        }
        sm_mock.describe_endpoint.return_value = {
            "ProductionVariants": [{
                "VariantName": "AllTraffic",
                "CurrentInstanceCount": 4,
                "DesiredInstanceCount": 4,
                "ManagedInstanceScaling": {"MaxInstanceCount": 4},
            }]
        }
        mock_gc.return_value = sm_mock

        skill = CapacityPlannerSkill()
        findings = skill._check_sagemaker_capacity("us-east-1", "test")
        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH


class TestEstimateHourly:
    def test_known_instance(self):
        skill = CapacityPlannerSkill()
        assert skill._estimate_hourly("p4d.24xlarge") == 32.77

    def test_unknown_instance(self):
        skill = CapacityPlannerSkill()
        assert skill._estimate_hourly("unknown.type") == 0.50
