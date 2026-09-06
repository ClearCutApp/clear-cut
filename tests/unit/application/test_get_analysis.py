"""Unit tests for `GetAnalysis` (ADR 0013).

The clock is injected and `stale_after` is a constructor argument, so the
reaper's boundary is provable without waiting thirty minutes and without a
clock read (AGENT.md Section 5). The store fake counts its writes, because
half of what this use case promises is that a healthy poll does not write.
"""

from datetime import UTC, datetime, timedelta

import pytest

from clearcut.application.get_analysis import STALE_AFTER, GetAnalysis
from clearcut.application.ports import AnalysisJobStore
from clearcut.domain.analysis import AnalysisJob, AnalysisState
from clearcut.domain.errors import RecordNotFound

_NOW = datetime(2026, 9, 5, 12, 0, 0, tzinfo=UTC)
_STALE_AFTER = timedelta(minutes=30)


class _JobStore:
    def __init__(self, jobs: list[AnalysisJob] | None = None) -> None:
        self._jobs = {(job.project_id, job.analysis_id): job for job in (jobs or [])}
        self.saved: list[AnalysisJob] = []

    def save(self, job: AnalysisJob) -> None:
        self.saved.append(job)
        self._jobs[(job.project_id, job.analysis_id)] = job

    def get(self, project_id: str, analysis_id: str) -> AnalysisJob:
        try:
            return self._jobs[(project_id, analysis_id)]
        except KeyError:
            raise RecordNotFound(f"no analysis {analysis_id!r} in project {project_id!r}") from None


def _job(
    state: AnalysisState = AnalysisState.RUNNING,
    updated_at: datetime = _NOW,
    version: int = 2,
) -> AnalysisJob:
    return AnalysisJob(
        analysis_id="ana-1",
        project_id="proj-1",
        script_id="scr-1",
        state=state,
        created_at=_NOW,
        updated_at=updated_at,
        version=version,
    )


def _use_case(store: _JobStore, now: datetime = _NOW) -> GetAnalysis:
    return GetAnalysis(store, clock=lambda: now, stale_after=_STALE_AFTER)


# The fake bound to its port by an annotated assignment (CP-012, D3).
_jobs_conforms: AnalysisJobStore = _JobStore()


def test_the_job_store_fake_satisfies_its_port() -> None:
    assert isinstance(_jobs_conforms, AnalysisJobStore)


def test_the_shipped_deadline_is_thirty_minutes() -> None:
    assert STALE_AFTER == timedelta(minutes=30)


def test_an_unknown_analysis_id_raises_record_not_found() -> None:
    # Propagated, not translated: the route maps it to 404, and a poll for an
    # analysis nobody queued is exactly that.
    use_case = _use_case(_JobStore())

    with pytest.raises(RecordNotFound):
        use_case.execute("proj-1", "ana-1")


def test_a_running_job_inside_the_deadline_is_returned_untouched() -> None:
    running = _job(updated_at=_NOW - timedelta(minutes=5))
    store = _JobStore([running])
    use_case = _use_case(store)

    assert use_case.execute("proj-1", "ana-1") == running
    assert store.saved == []


def test_a_job_exactly_at_the_deadline_is_not_yet_stale_and_is_not_written() -> None:
    # `AnalysisJob.is_stale` compares with `>`, so the deadline itself is
    # still a live run. Reaping here would fail a job one tick before the
    # write that would have cleared it.
    running = _job(updated_at=_NOW - _STALE_AFTER)
    store = _JobStore([running])
    use_case = _use_case(store)

    result = use_case.execute("proj-1", "ana-1")

    assert result.state is AnalysisState.RUNNING
    assert store.saved == []


def test_a_job_one_second_past_the_deadline_is_reaped_into_failed() -> None:
    running = _job(updated_at=_NOW - _STALE_AFTER - timedelta(seconds=1))
    store = _JobStore([running])
    use_case = _use_case(store)

    result = use_case.execute("proj-1", "ana-1")

    assert result.state is AnalysisState.FAILED
    assert result.version == 3
    assert result.updated_at == _NOW


def test_the_reaped_job_is_written_back_so_the_next_poll_reads_the_failure() -> None:
    # An instance reclaimed mid-run has nothing left to write its own
    # failure, so the read that finds the row stale is what records it
    # (ADR 0013).
    running = _job(updated_at=_NOW - timedelta(hours=2))
    store = _JobStore([running])
    use_case = _use_case(store)

    result = use_case.execute("proj-1", "ana-1")

    assert store.saved == [result]
    assert store.get("proj-1", "ana-1") == result


def test_the_reaped_jobs_error_names_the_timeout() -> None:
    running = _job(updated_at=_NOW - timedelta(hours=2))
    use_case = _use_case(_JobStore([running]))

    result = use_case.execute("proj-1", "ana-1")

    assert "timed out" in result.error
    assert "30 minutes" in result.error


def test_a_queued_job_past_the_deadline_is_left_alone() -> None:
    # `is_stale` is RUNNING-only: a job still QUEUED has not started, and
    # failing it would blame the run for the queue.
    queued = _job(state=AnalysisState.QUEUED, updated_at=_NOW - timedelta(hours=2), version=1)
    store = _JobStore([queued])
    use_case = _use_case(store)

    assert use_case.execute("proj-1", "ana-1") == queued
    assert store.saved == []


def test_a_finished_job_is_never_reaped_however_old_it_is() -> None:
    # SUCCEEDED is terminal and `AnalysisJob.failed` raises on it, so a
    # reaper that ignored the state would turn every old completed analysis
    # into a 500 on read.
    finished = _job(state=AnalysisState.SUCCEEDED, updated_at=_NOW - timedelta(days=30), version=3)
    store = _JobStore([finished])
    use_case = _use_case(store)

    assert use_case.execute("proj-1", "ana-1") == finished
    assert store.saved == []
