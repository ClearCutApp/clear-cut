"""Transactional execution invariants; these are not live Firestore proofs."""

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

import pytest

from clearcut.adapters.gcp.analysis_jobs import FirestoreAnalysisJobs
from clearcut.domain.durable_analysis import AnalysisBusy, AnalysisCancelled, LeaseLost, NewAnalysis
from clearcut.domain.identity import AccessDenied
from clearcut.domain.screenplay import ContentReference, Revision
from tests.unit.adapters.test_clearance_transactions import AtomicClient

NOW = datetime(2026, 9, 6, tzinfo=UTC)


def configured() -> tuple[AtomicClient, FirestoreAnalysisJobs, Revision, NewAnalysis]:
    client = AtomicClient()
    content = ContentReference("gs://bucket/immutable", "sha", 10)
    revision = Revision("revision-1", "project", 1, content, "writer", NOW.isoformat())
    client.data = {
        "project_access/project": {"organization_id": "org", "grants": {"writer": "writer"}},
        "organizations/org/members/writer": {"active": True, "role": "writer"},
        "project_access/project/revisions/revision-1": asdict(revision),
    }
    command = NewAnalysis(
        "analysis", "script", "project", "org", "writer", "revision-1", "AR", "{}", NOW
    )
    return client, FirestoreAnalysisJobs(client), revision, command


def test_request_and_launch_intent_commit_before_claim_and_duplicate_enqueue_is_one_job():
    client, jobs, revision, command = configured()
    queued = jobs.enqueue(command, revision)
    assert queued.request.revision_content == revision.content
    assert client.data["analysis_launches/analysis"]["state"] == "pending"
    assert jobs.enqueue(command, revision) == queued
    assert client.data["project_access/project"]["analysis_sequence"] == 1
    with pytest.raises(AnalysisBusy):
        jobs.enqueue(replace(command, analysis_id="second"), revision)
    assert "analysis_jobs/second" not in client.data


def test_revocation_blocks_enqueue_without_partial_launch_or_sequence():
    client, jobs, revision, command = configured()
    client.data["organizations/org/members/writer"]["active"] = False
    with pytest.raises(AccessDenied):
        jobs.enqueue(command, revision)
    assert not any(key.startswith("analysis_") for key in client.data)
    assert "analysis_sequence" not in client.data["project_access/project"]


def test_stopped_worker_resumes_with_new_fence_and_old_worker_cannot_checkpoint():
    _, jobs, revision, command = configured()
    jobs.enqueue(command, revision)
    first = jobs.claim("analysis", "worker-one", NOW)
    assert first is not None
    assert jobs.claim("analysis", "duplicate", NOW) is None
    saved = ContentReference("gs://bucket/checkpoint", "digest", 20)
    jobs.checkpoint("analysis", "worker-one", first.fence, "extraction", saved, NOW)
    later = NOW + timedelta(seconds=91)
    second = jobs.claim("analysis", "worker-two", later)
    assert second is not None and second.fence == first.fence + 1
    assert jobs.read_checkpoint("analysis", "extraction") == saved
    with pytest.raises(LeaseLost):
        jobs.checkpoint(
            "analysis", "worker-one", first.fence, "extraction", revision.content, later
        )
    assert jobs.read_checkpoint("analysis", "extraction") == saved


def test_cancellation_blocks_heartbeat_and_checkpoint_and_cannot_be_reclaimed():
    _, jobs, revision, command = configured()
    jobs.enqueue(command, revision)
    job = jobs.claim("analysis", "worker", NOW)
    assert job is not None
    jobs.request_cancel("project", "analysis", "writer", NOW)
    with pytest.raises(AnalysisCancelled):
        jobs.heartbeat("analysis", "worker", job.fence, NOW)
    assert jobs.claim("analysis", "new-worker", NOW + timedelta(minutes=2)) is None


def test_retry_backoff_and_attempt_budget_are_persisted():
    _, jobs, revision, command = configured()
    jobs.enqueue(command, revision)
    at = NOW
    for attempt in range(1, 5):
        job = jobs.claim("analysis", "worker", at)
        assert job is not None and job.attempt == attempt
        jobs.fail("analysis", "worker", job.fence, "provider_unavailable", at, True)
        assert jobs.claim("analysis", "too-soon", at) is None
        at += timedelta(minutes=6)
    assert jobs.load("analysis").state == "FAILED"
    assert jobs.claim("analysis", "fifth", at) is None
