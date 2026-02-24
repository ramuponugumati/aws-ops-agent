"""Tests for CostOpt Intelligence skill."""
import pytest
from unittest.mock import patch, MagicMock
from ops_agent.skills.costopt_intelligence import CostOptIntelligenceSkill
from ops_agent.core import Severity


@pytest.fixture
def skill():
    return CostOptIntelligenceSkill()


class TestCostOptMetadata:
    def test_name(self, skill):
        assert skill.name == "costopt-intelligence"

    def test_description(self, skill):
        assert "Savings Plan" in skill.description


class TestSavingsPlanRecommendations:
    @patch("ops_agent.skills.costopt_intelligence.get_client")
    def test_finds_sp_opportunity(self, mock_gc):
        ce_mock = MagicMock()
        ce_mock.get_savings_plans_purchase_recommendation.return_value = {
            "SavingsPlansPurchaseRecommendation": {
                "SavingsPlansPurchaseRecommendationDetails": [{
                    "HourlyCommitmentToPurchase": "1.50",
                    "EstimatedMonthlySavingsAmount": "300",
                    "EstimatedOnDemandCost": "1000",
                    "EstimatedSavingsPercentage": "30",
                }]
            }
        }
        mock_gc.return_value = ce_mock

        skill = CostOptIntelligenceSkill()
        findings = skill._check_savings_plan_recommendations("test")
        assert len(findings) >= 1
        sp_findings = [f for f in findings if "SP opportunity" in f.title]
        assert len(sp_findings) >= 1
        assert sp_findings[0].monthly_impact == 300.0

    @patch("ops_agent.skills.costopt_intelligence.get_client")
    def test_ignores_tiny_savings(self, mock_gc):
        ce_mock = MagicMock()
        ce_mock.get_savings_plans_purchase_recommendation.return_value = {
            "SavingsPlansPurchaseRecommendation": {
                "SavingsPlansPurchaseRecommendationDetails": [{
                    "HourlyCommitmentToPurchase": "0.01",
                    "EstimatedMonthlySavingsAmount": "5",
                    "EstimatedOnDemandCost": "20",
                    "EstimatedSavingsPercentage": "25",
                }]
            }
        }
        mock_gc.return_value = ce_mock

        skill = CostOptIntelligenceSkill()
        findings = skill._check_savings_plan_recommendations("test")
        # $5/mo savings should be filtered out (< $50 threshold)
        assert len(findings) == 0


class TestRIUtilization:
    @patch("ops_agent.skills.costopt_intelligence.get_client")
    def test_finds_low_ri_utilization(self, mock_gc):
        ce_mock = MagicMock()
        ce_mock.get_reservation_utilization.return_value = {
            "UtilizationsByTime": [{
                "Total": {
                    "UtilizationPercentage": "45",
                    "UnusedHours": "500",
                    "TotalAmortizedFee": "2000",
                }
            }]
        }
        ce_mock.get_reservation_coverage.return_value = {"CoveragesByTime": []}
        mock_gc.return_value = ce_mock

        skill = CostOptIntelligenceSkill()
        findings = skill._check_ri_utilization("test")
        util_findings = [f for f in findings if "RI utilization" in f.title]
        assert len(util_findings) == 1
        assert util_findings[0].severity == Severity.HIGH  # < 50%

    @patch("ops_agent.skills.costopt_intelligence.get_client")
    def test_good_ri_utilization_not_flagged(self, mock_gc):
        ce_mock = MagicMock()
        ce_mock.get_reservation_utilization.return_value = {
            "UtilizationsByTime": [{
                "Total": {"UtilizationPercentage": "95", "UnusedHours": "10", "TotalAmortizedFee": "1000"}
            }]
        }
        ce_mock.get_reservation_coverage.return_value = {"CoveragesByTime": []}
        mock_gc.return_value = ce_mock

        skill = CostOptIntelligenceSkill()
        findings = skill._check_ri_utilization("test")
        assert len(findings) == 0

    @patch("ops_agent.skills.costopt_intelligence.get_client")
    def test_finds_low_ri_coverage(self, mock_gc):
        ce_mock = MagicMock()
        ce_mock.get_reservation_utilization.return_value = {"UtilizationsByTime": []}
        ce_mock.get_reservation_coverage.return_value = {
            "CoveragesByTime": [{
                "Total": {"CoverageHours": {"CoverageHoursPercentage": "30", "OnDemandHours": "1000"}}
            }]
        }
        mock_gc.return_value = ce_mock

        skill = CostOptIntelligenceSkill()
        findings = skill._check_ri_utilization("test")
        cov_findings = [f for f in findings if "RI coverage" in f.title]
        assert len(cov_findings) == 1


class TestRightsizing:
    @patch("ops_agent.skills.costopt_intelligence.get_client")
    def test_finds_oversized_instance(self, mock_gc):
        ec2_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Reservations": [{"Instances": [
                {"InstanceId": "i-big", "InstanceType": "m5.4xlarge",
                 "Tags": [{"Key": "Name", "Value": "web-server"}]},
            ]}]}
        ]
        ec2_mock.get_paginator.return_value = paginator

        cw_mock = MagicMock()
        # Low CPU: avg 8%, max 25%
        cw_mock.get_metric_statistics.side_effect = [
            {"Datapoints": [{"Average": 8.0, "Maximum": 25.0}]},  # CPU
            {"Datapoints": [{"Average": 500000}]},  # Network
        ]

        def side_effect(service, region, profile):
            if service == "ec2":
                return ec2_mock
            return cw_mock
        mock_gc.side_effect = side_effect

        skill = CostOptIntelligenceSkill()
        findings = skill._check_rightsizing("us-east-1", "test")
        assert len(findings) == 1
        assert "Right-size" in findings[0].title
        assert "2xlarge" in findings[0].title  # should suggest one size down
        assert findings[0].monthly_impact > 0

    @patch("ops_agent.skills.costopt_intelligence.get_client")
    def test_busy_instance_not_flagged(self, mock_gc):
        ec2_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Reservations": [{"Instances": [
                {"InstanceId": "i-busy", "InstanceType": "m5.2xlarge", "Tags": []},
            ]}]}
        ]
        ec2_mock.get_paginator.return_value = paginator

        cw_mock = MagicMock()
        cw_mock.get_metric_statistics.side_effect = [
            {"Datapoints": [{"Average": 65.0, "Maximum": 90.0}]},  # CPU high
            {"Datapoints": [{"Average": 5000000}]},
        ]

        def side_effect(service, region, profile):
            if service == "ec2":
                return ec2_mock
            return cw_mock
        mock_gc.side_effect = side_effect

        skill = CostOptIntelligenceSkill()
        findings = skill._check_rightsizing("us-east-1", "test")
        assert len(findings) == 0


class TestEBSOptimization:
    @patch("ops_agent.skills.costopt_intelligence.get_client")
    def test_finds_gp2_volumes(self, mock_gc):
        ec2_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Volumes": [
                {"VolumeId": "vol-gp2", "Size": 500, "VolumeType": "gp2"},
            ]}
        ]
        ec2_mock.get_paginator.return_value = paginator
        mock_gc.return_value = ec2_mock

        skill = CostOptIntelligenceSkill()
        findings = skill._check_ebs_gp2_to_gp3("us-east-1", "test")
        assert len(findings) == 1
        assert "GP2→GP3" in findings[0].title
        assert findings[0].monthly_impact == 10.0  # 500 * (0.10 - 0.08)

    @patch("ops_agent.skills.costopt_intelligence.get_client")
    def test_tiny_volume_not_flagged(self, mock_gc):
        ec2_mock = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Volumes": [{"VolumeId": "vol-tiny", "Size": 8, "VolumeType": "gp2"}]}
        ]
        ec2_mock.get_paginator.return_value = paginator
        mock_gc.return_value = ec2_mock

        skill = CostOptIntelligenceSkill()
        findings = skill._check_ebs_gp2_to_gp3("us-east-1", "test")
        assert len(findings) == 0  # $0.16 savings, below $1 threshold


class TestS3Tiering:
    @patch("ops_agent.skills.costopt_intelligence.get_client")
    def test_finds_large_standard_bucket(self, mock_gc):
        s3_mock = MagicMock()
        s3_mock.list_buckets.return_value = {"Buckets": [{"Name": "big-bucket"}]}

        cw_mock = MagicMock()
        def smart_cw(**kwargs):
            dims = {d["Name"]: d["Value"] for d in kwargs.get("Dimensions", [])}
            if dims.get("StorageType") == "StandardStorage":
                return {"Datapoints": [{"Average": 1000 * 1024 ** 3}]}  # 1TB
            return {"Datapoints": []}
        cw_mock.get_metric_statistics = smart_cw

        clients = {"s3": s3_mock, "cloudwatch": cw_mock}
        mock_gc.side_effect = lambda svc, *a, **kw: clients.get(svc, MagicMock())

        skill = CostOptIntelligenceSkill()
        findings = skill._check_s3_tiering("test")
        assert len(findings) == 1
        assert "tiering" in findings[0].title.lower()
        assert findings[0].monthly_impact > 0


class TestNATDataCosts:
    @patch("ops_agent.skills.costopt_intelligence.get_client")
    def test_finds_expensive_nat(self, mock_gc):
        ec2_mock = MagicMock()
        ec2_mock.describe_nat_gateways.return_value = {
            "NatGateways": [{"NatGatewayId": "nat-expensive", "VpcId": "vpc-123"}]
        }
        cw_mock = MagicMock()
        # 2TB/week = ~$387/mo in data processing
        cw_mock.get_metric_statistics.return_value = {
            "Datapoints": [{"Sum": 2 * 1024 ** 4}]  # 2TB
        }

        def side_effect(service, region, profile):
            if service == "ec2":
                return ec2_mock
            return cw_mock
        mock_gc.side_effect = side_effect

        skill = CostOptIntelligenceSkill()
        findings = skill._check_nat_data_costs("us-east-1", "test")
        assert len(findings) == 1
        assert "NAT data cost" in findings[0].title
        assert "VPC Gateway Endpoints" in findings[0].recommended_action

    @patch("ops_agent.skills.costopt_intelligence.get_client")
    def test_low_traffic_nat_not_flagged(self, mock_gc):
        ec2_mock = MagicMock()
        ec2_mock.describe_nat_gateways.return_value = {
            "NatGateways": [{"NatGatewayId": "nat-low", "VpcId": "vpc-456"}]
        }
        cw_mock = MagicMock()
        cw_mock.get_metric_statistics.return_value = {
            "Datapoints": [{"Sum": 1 * 1024 ** 3}]  # 1GB — cheap
        }

        def side_effect(service, region, profile):
            if service == "ec2":
                return ec2_mock
            return cw_mock
        mock_gc.side_effect = side_effect

        skill = CostOptIntelligenceSkill()
        findings = skill._check_nat_data_costs("us-east-1", "test")
        assert len(findings) == 0


class TestExpiringCommitments:
    @patch("ops_agent.skills.costopt_intelligence.get_client")
    def test_finds_expiring_sp(self, mock_gc):
        from datetime import datetime, timedelta, timezone
        ce_mock = MagicMock()
        expiry = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
        ce_mock.get_savings_plans_utilization_details.return_value = {
            "SavingsPlansUtilizationDetails": [{
                "Attributes": {"EndDateTime": expiry},
                "Utilization": {"TotalCommitment": "500"},
            }]
        }
        mock_gc.return_value = ce_mock

        skill = CostOptIntelligenceSkill()
        findings = skill._check_expiring_commitments("test")
        assert len(findings) == 1
        assert "expiring" in findings[0].title.lower()
        assert findings[0].severity == Severity.HIGH  # < 30 days
