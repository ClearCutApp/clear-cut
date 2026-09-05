"""Tests for AnalysisJob and AnalysisState (docs/plan/sdd.md Section 4.1)."""

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from clearcut.domain.analysis import AnalysisJob, AnalysisState

_CREATED_AT = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 8, 30, 12, 5, 0, tzinfo=UTC)
_REAPER_WINDOW = timedelta(minutes=15)


def _job(
    state: AnalysisState = AnalysisState.QUEUED,
    version: int = 1,
    analysis_id: str = "ana-1",
    project_id: str = "proj-1",
    script_id: str = "scr-1",
    updated_at: datetime = _CREATED_AT,
    error: str = "",
) -> AnalysisJob:
    return AnalysisJob(
        analysis_id=analysis_id,
        project_id=project_id,
        script_id=script_id,
        state=state,
        created_at=_CREATED_AT,
        updated_at=updated_at,
        error=error,
        version=version,
    )


def test_defaults_error_to_the_empty_string():
    assert _job().error == ""


def test_defaults_version_to_one():
    job = AnalysisJob(
        analysis_id="ana-1",
        project_id="proj-1",
        script_id="scr-1",
        state=AnalysisState.QUEUED,
        created_at=_CREATED_AT,
        updated_at=_CREATED_AT,
    )
    assert job.version == 1


def test_analysis_job_is_frozen():
    job = _job()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(job, "state", AnalysisState.RUNNING)


def test_rejects_a_version_below_one():
    with pytest.raises(ValueError):
        _job(version=0)


@pytest.mark.parametrize("blank", ["", "   "])
def test_rejects_a_blank_or_whitespace_only_analysis_id(blank):
    with pytest.raises(ValueError):
        _job(analysis_id=blank)


@pytest.mark.parametrize("blank", ["", "   "])
def test_rejects_a_blank_or_whitespace_only_project_id(blank):
    with pytest.raises(ValueError):
        _job(project_id=blank)


@pytest.mark.parametrize("blank", ["", "   "])
def test_rejects_a_blank_or_whitespace_only_script_id(blank):
    with pytest.raises(ValueError):
        _job(script_id=blank)


def test_running_returns_a_new_job_at_the_next_version():
    original = _job(state=AnalysisState.QUEUED, version=1)
    updated = original.running(at=_LATER)

    assert updated.state == AnalysisState.RUNNING
    assert updated.version == 2
    assert updated.updated_at == _LATER


def test_running_leaves_the_receiver_unchanged():
    original = _job(state=AnalysisState.QUEUED, version=1)
    original.running(at=_LATER)

    assert original.state == AnalysisState.QUEUED
    assert original.version == 1
    assert original.updated_at == _CREATED_AT


def test_running_carries_created_at_and_the_identifiers_unchanged():
    original = _job(state=AnalysisState.QUEUED)
    updated = original.running(at=_LATER)

    assert updated.created_at == original.created_at
    assert updated.analysis_id == original.analysis_id
    assert updated.project_id == original.project_id
    assert updated.script_id == original.script_id


def test_succeeded_returns_a_new_job_at_the_next_version():
    original = _job(state=AnalysisState.RUNNING, version=2)
    updated = original.succeeded(at=_LATER)

    assert updated.state == AnalysisState.SUCCEEDED
    assert updated.version == 3
    assert updated.updated_at == _LATER


def test_succeeded_leaves_the_receiver_unchanged():
    original = _job(state=AnalysisState.RUNNING, version=2)
    original.succeeded(at=_LATER)

    assert original.state == AnalysisState.RUNNING
    assert original.version == 2


def test_succeeded_leaves_error_empty():
    updated = _job(state=AnalysisState.RUNNING).succeeded(at=_LATER)
    assert updated.error == ""


def test_failed_records_the_reason_at_the_next_version():
    original = _job(state=AnalysisState.RUNNING, version=2)
    updated = original.failed("Document AI returned no pages", at=_LATER)

    assert updated.state == AnalysisState.FAILED
    assert updated.error == "Document AI returned no pages"
    assert updated.version == 3
    assert updated.updated_at == _LATER


def test_failed_leaves_the_receiver_unchanged():
    original = _job(state=AnalysisState.RUNNING, version=2)
    original.failed("Document AI returned no pages", at=_LATER)

    assert original.state == AnalysisState.RUNNING
    assert original.error == ""
    assert original.version == 2


@pytest.mark.parametrize("blank_reason", ["", "   "])
def test_failed_rejects_a_blank_or_whitespace_only_reason(blank_reason):
    original = _job(state=AnalysisState.RUNNING)
    with pytest.raises(ValueError):
        original.failed(blank_reason, at=_LATER)


@pytest.mark.parametrize("state", [AnalysisState.QUEUED, AnalysisState.RUNNING])
def test_an_unfinished_job_accepts_every_transition(state):
    job = _job(state=state)

    assert job.running(at=_LATER).state == AnalysisState.RUNNING
    assert job.succeeded(at=_LATER).state == AnalysisState.SUCCEEDED
    assert job.failed("upstream timed out", at=_LATER).state == AnalysisState.FAILED


@pytest.mark.parametrize("terminal", [AnalysisState.SUCCEEDED, AnalysisState.FAILED])
@pytest.mark.parametrize(
    "transition",
    [
        lambda job: job.running(at=_LATER),
        lambda job: job.succeeded(at=_LATER),
        lambda job: job.failed("upstream timed out", at=_LATER),
    ],
    ids=["running", "succeeded", "failed"],
)
def test_a_finished_job_refuses_every_transition(terminal, transition):
    job = _job(state=terminal, error="upstream timed out")
    with pytest.raises(ValueError):
        transition(job)


def test_a_running_job_is_not_stale_at_exactly_the_window():
    job = _job(state=AnalysisState.RUNNING, updated_at=_CREATED_AT)
    now = _CREATED_AT + _REAPER_WINDOW

    assert job.is_stale(now, _REAPER_WINDOW) is False


def test_a_running_job_is_stale_one_microsecond_past_the_window():
    job = _job(state=AnalysisState.RUNNING, updated_at=_CREATED_AT)
    now = _CREATED_AT + _REAPER_WINDOW + timedelta(microseconds=1)

    assert job.is_stale(now, _REAPER_WINDOW) is True


def test_a_running_job_is_not_stale_before_the_window():
    job = _job(state=AnalysisState.RUNNING, updated_at=_CREATED_AT)
    now = _CREATED_AT + timedelta(minutes=1)

    assert job.is_stale(now, _REAPER_WINDOW) is False


@pytest.mark.parametrize(
    "state",
    [AnalysisState.QUEUED, AnalysisState.SUCCEEDED, AnalysisState.FAILED],
)
def test_a_job_that_is_not_running_is_never_stale_however_old(state):
    job = _job(state=state, updated_at=_CREATED_AT, error="upstream timed out")
    now = _CREATED_AT + timedelta(days=365)

    assert job.is_stale(now, _REAPER_WINDOW) is False


def test_is_stale_leaves_the_receiver_unchanged():
    job = _job(state=AnalysisState.RUNNING, version=2)
    job.is_stale(_CREATED_AT + timedelta(days=1), _REAPER_WINDOW)

    assert job.state == AnalysisState.RUNNING
    assert job.version == 2
    assert job.updated_at == _CREATED_AT
