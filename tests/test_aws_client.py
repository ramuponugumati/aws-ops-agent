"""Tests for aws_client module — session management, region discovery, org tree."""
import pytest
from unittest.mock import patch, MagicMock, call
from ops_agent.aws_client import (
    get_session, get_client, get_regions, get_account_id,
    parallel_regions, build_org_tree, assume_role_session,
)


class TestGetSession:
    @patch("ops_agent.aws_client.boto3.Session")
    def test_default_session(self, mock_session_cls):
        get_session()
        mock_session_cls.assert_called_once_with()

    @patch("ops_agent.aws_client.boto3.Session")
    def test_session_with_profile(self, mock_session_cls):
        get_session(profile="my-profile")
        mock_session_cls.assert_called_once_with(profile_name="my-profile")

    @patch("ops_agent.aws_client.boto3.Session")
    def test_session_with_region(self, mock_session_cls):
        get_session(region="eu-west-1")
        mock_session_cls.assert_called_once_with(region_name="eu-west-1")

    @patch("ops_agent.aws_client.boto3.Session")
    def test_session_with_both(self, mock_session_cls):
        get_session(region="eu-west-1", profile="prod")
        mock_session_cls.assert_called_once_with(profile_name="prod", region_name="eu-west-1")


class TestGetRegions:
    def test_single_region_returns_list(self):
        assert get_regions(region="us-east-1") == ["us-east-1"]

    @patch("ops_agent.aws_client.get_client")
    def test_all_regions(self, mock_gc):
        ec2_mock = MagicMock()
        ec2_mock.describe_regions.return_value = {
            "Regions": [
                {"RegionName": "us-east-1"},
                {"RegionName": "us-west-2"},
                {"RegionName": "eu-west-1"},
            ]
        }
        mock_gc.return_value = ec2_mock
        regions = get_regions(region=None, profile="test")
        assert len(regions) == 3
        assert "us-east-1" in regions


class TestGetAccountId:
    @patch("ops_agent.aws_client.get_client")
    def test_returns_account_id(self, mock_gc):
        sts_mock = MagicMock()
        sts_mock.get_caller_identity.return_value = {"Account": "111222333444"}
        mock_gc.return_value = sts_mock
        assert get_account_id("test") == "111222333444"


class TestParallelRegions:
    def test_parallel_regions_aggregates(self):
        def scanner(region):
            return [f"finding-{region}"]
        results = parallel_regions(scanner, ["us-east-1", "us-west-2"])
        assert len(results) == 2
        assert "finding-us-east-1" in results
        assert "finding-us-west-2" in results

    def test_parallel_regions_handles_exceptions(self):
        def scanner(region):
            if region == "us-west-2":
                raise RuntimeError("boom")
            return [f"finding-{region}"]
        results = parallel_regions(scanner, ["us-east-1", "us-west-2"])
        assert len(results) == 1
        assert "finding-us-east-1" in results

    def test_parallel_regions_empty(self):
        results = parallel_regions(lambda r: [], ["us-east-1"])
        assert results == []


class TestBuildOrgTree:
    @patch("ops_agent.aws_client.get_client")
    def test_build_org_tree(self, mock_gc):
        org_mock = MagicMock()
        org_mock.list_roots.return_value = {"Roots": [{"Id": "r-root1"}]}
        org_mock.list_organizational_units_for_parent.return_value = {
            "OrganizationalUnits": [
                {"Id": "ou-prod", "Name": "Production"},
                {"Id": "ou-dev", "Name": "Development"},
            ]
        }
        paginator_mock = MagicMock()
        paginator_mock.paginate.return_value = [
            {"Accounts": [{"Id": "111111111111", "Name": "Prod-1", "Status": "ACTIVE"}]}
        ]
        org_mock.get_paginator.return_value = paginator_mock
        mock_gc.return_value = org_mock

        tree = build_org_tree("test")
        assert "Production" in tree
        assert "Development" in tree
        assert len(tree["Production"]["accounts"]) == 1
        assert tree["Production"]["accounts"][0]["id"] == "111111111111"

    @patch("ops_agent.aws_client.get_client")
    def test_build_org_tree_skips_suspended(self, mock_gc):
        org_mock = MagicMock()
        org_mock.list_roots.return_value = {"Roots": [{"Id": "r-root1"}]}
        org_mock.list_organizational_units_for_parent.return_value = {
            "OrganizationalUnits": [{"Id": "ou-1", "Name": "OU1"}]
        }
        paginator_mock = MagicMock()
        paginator_mock.paginate.return_value = [
            {"Accounts": [
                {"Id": "111", "Name": "Active", "Status": "ACTIVE"},
                {"Id": "222", "Name": "Suspended", "Status": "SUSPENDED"},
            ]}
        ]
        org_mock.get_paginator.return_value = paginator_mock
        mock_gc.return_value = org_mock

        tree = build_org_tree()
        assert len(tree["OU1"]["accounts"]) == 1


class TestAssumeRoleSession:
    @patch("ops_agent.aws_client.get_session")
    def test_assume_role(self, mock_get_session):
        sts_mock = MagicMock()
        sts_mock.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "AKIA_TEMP",
                "SecretAccessKey": "secret_temp",
                "SessionToken": "token_temp",
            }
        }
        session_mock = MagicMock()
        session_mock.client.return_value = sts_mock
        mock_get_session.return_value = session_mock

        creds = assume_role_session("999888777666", "MyRole", "test")
        assert creds["AccessKeyId"] == "AKIA_TEMP"
        sts_mock.assume_role.assert_called_once()
        call_kwargs = sts_mock.assume_role.call_args[1]
        assert "999888777666" in call_kwargs["RoleArn"]
        assert "MyRole" in call_kwargs["RoleArn"]
