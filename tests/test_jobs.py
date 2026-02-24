"""Tests for job store."""
import pytest
from ops_agent.dashboard.jobs import JobStore, ScanJob, ScanJobStatus


class TestJobStore:
    def test_create_job(self):
        store = JobStore()
        job = store.create(["zombie-hunter", "cost-anomaly"])
        assert job.status == ScanJobStatus.PENDING
        assert job.skill_names == ["zombie-hunter", "cost-anomaly"]
        assert job.id is not None
        assert job.created_at is not None
        assert job.completed_at is None

    def test_get_job(self):
        store = JobStore()
        job = store.create(["zombie-hunter"])
        retrieved = store.get(job.id)
        assert retrieved is job

    def test_get_nonexistent(self):
        store = JobStore()
        assert store.get("nonexistent-id") is None

    def test_update_status(self):
        store = JobStore()
        job = store.create(["zombie-hunter"])
        store.update(job.id, status=ScanJobStatus.RUNNING)
        assert store.get(job.id).status == ScanJobStatus.RUNNING

    def test_update_completed_sets_timestamp(self):
        store = JobStore()
        job = store.create(["zombie-hunter"])
        store.update(job.id, status=ScanJobStatus.COMPLETED, results=[])
        assert store.get(job.id).completed_at is not None

    def test_update_failed_sets_timestamp(self):
        store = JobStore()
        job = store.create(["zombie-hunter"])
        store.update(job.id, status=ScanJobStatus.FAILED, error="boom")
        assert store.get(job.id).completed_at is not None
        assert store.get(job.id).error == "boom"

    def test_list_all_sorted(self):
        store = JobStore()
        j1 = store.create(["a"])
        j2 = store.create(["b"])
        j3 = store.create(["c"])
        jobs = store.list_all()
        # Most recent first
        assert jobs[0].id == j3.id
        assert jobs[-1].id == j1.id

    def test_update_nonexistent_no_error(self):
        store = JobStore()
        store.update("fake-id", status=ScanJobStatus.RUNNING)  # Should not raise
