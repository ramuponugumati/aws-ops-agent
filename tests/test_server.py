"""Tests for FastAPI dashboard server."""
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from ops_agent.dashboard.server import create_app
from ops_agent.core import SkillResult, Finding, Severity


@pytest.fixture
def client():
    app = create_app(profile="test-profile")
    return TestClient(app)


class TestHealthAndRoot:
    def test_root_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_static_css(self, client):
        resp = client.get("/static/css/styles.css")
        # May or may not exist depending on file system, but should not 500
        assert resp.status_code in (200, 404)


class TestSkillsAPI:
    def test_list_skills(self, client):
        resp = client.get("/api/skills")
        assert resp.status_code == 200
        skills = resp.json()
        assert isinstance(skills, list)
        assert len(skills) == 12  # 12 registered skills
        names = [s["name"] for s in skills]
        assert "zombie-hunter" in names
        assert "cost-anomaly" in names
        assert "security-posture" in names
        assert "arch-diagram" in names


class TestScanAPI:
    def test_scan_unknown_skill(self, client):
        resp = client.post("/api/scan/nonexistent-skill", json={})
        assert resp.status_code == 400
        assert "Unknown skill" in resp.json()["detail"]

    def test_scan_valid_skill_returns_job(self, client):
        resp = client.post("/api/scan/zombie-hunter", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "pending"

    def test_scan_all_returns_job(self, client):
        resp = client.post("/api/scan-all", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data


class TestJobsAPI:
    def test_get_nonexistent_job(self, client):
        resp = client.get("/api/jobs/fake-job-id")
        assert resp.status_code == 404

    def test_get_job_results_not_completed(self, client):
        # Manually create a job via the store to avoid race conditions
        from ops_agent.dashboard.jobs import ScanJobStatus
        store = client.app.state.job_store
        job = store.create(["zombie-hunter"])
        # Job is PENDING, not completed
        resp = client.get(f"/api/jobs/{job.id}/results")
        assert resp.status_code == 400
        assert "not completed" in resp.json()["detail"]


class TestRemediateAPI:
    def test_remediate_no_handler(self, client):
        finding = {"skill": "cost-anomaly", "title": "Cost spike", "resource_id": "x"}
        resp = client.post("/api/remediate", json={"finding": finding})
        assert resp.status_code == 400
        assert "No remediation" in resp.json()["detail"]

    @patch("ops_agent.dashboard.server.execute_remediation")
    def test_remediate_success(self, mock_exec, client):
        from ops_agent.dashboard.remediation import RemediationResult
        mock_exec.return_value = RemediationResult(
            success=True, finding_id="vol-abc", action="delete_ebs_volume",
            message="Deleted EBS volume vol-abc", timestamp="2025-01-01T00:00:00",
        )
        finding = {"skill": "zombie-hunter", "title": "Unattached EBS: vol-abc", "resource_id": "vol-abc", "region": "us-east-1"}
        resp = client.post("/api/remediate", json={"finding": finding})
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestChatAPI:
    @patch("ops_agent.dashboard.server.handle_chat")
    def test_chat_success(self, mock_chat, client):
        mock_chat.return_value = "Here are your findings..."
        resp = client.post("/api/chat", json={"message": "What are my findings?"})
        assert resp.status_code == 200
        assert resp.json()["response"] == "Here are your findings..."

    @patch("ops_agent.dashboard.server.handle_chat")
    def test_chat_bedrock_unavailable(self, mock_chat, client):
        from ops_agent.dashboard.chat import BedrockUnavailableError
        mock_chat.side_effect = BedrockUnavailableError("No access")
        resp = client.post("/api/chat", json={"message": "hello"})
        assert resp.status_code == 503

    def test_chat_empty_message(self, client):
        # Empty message now returns 400 due to input validation
        resp = client.post("/api/chat", json={"message": ""})
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()


class TestOrgScanAPI:
    def test_org_scan_returns_job(self, client):
        resp = client.post("/api/org-scan", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data

    def test_org_scan_invalid_skill(self, client):
        resp = client.post("/api/org-scan", json={"skill": "nonexistent"})
        assert resp.status_code == 400
