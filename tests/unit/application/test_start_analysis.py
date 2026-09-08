"""Unit tests for `StartAnalysis` (ADR 0013).

No `unittest.mock` and no clock read of the kind AGENT.md Section 5 bans: the
clock is a hand-written counter injected through the constructor, and the
runner is a synchronous stand-in that calls the work inline, so the whole
background path runs on the test's own thread and every assertion is
deterministic.

The two pipelines are hand-written stand-ins rather than real `AnalyzeScript`
and `EvaluateDelta` instances, which would need seventeen fakes between them
to build. `StartAnalysis` calls one method on each, and the seam being tested
is which of the two it calls -- so `cast` binds the stand-in to the declared
type at the one construction site, the way the port fakes elsewhere in this
suite bind structurally.
"""

import threading
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from clearcut.application.analyze_script import AnalysisReport, AnalyzeScript
from clearcut.application.evaluate_delta import EvaluateDelta
from clearcut.application.ports import AnalysisJobStore
from clearcut.application.start_analysis import (
    Runner,
    StartAnalysis,
    Work,
    run_in_background,
    utc_now,
)
from clearcut.domain.analysis import AnalysisJob, AnalysisState
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.jurisdiction import Jurisdiction, jurisdiction_for
from clearcut.domain.script import Script

_MEXICO = jurisdiction_for("MX")
_START = datetime(2026, 9, 5, 12, 0, 0, tzinfo=UTC)


class _Clock:
    """Ticks one minute per read, so every transition carries a distinct time."""

    def __init__(self, start: datetime = _START, step: timedelta = timedelta(minutes=1)) -> None:
        self._now = start
        self._step = step

    def __call__(self) -> datetime:
        now = self._now
        self._now += self._step
        return now


class _JobStore:
    def __init__(self) -> None:
        self.saved: list[AnalysisJob] = []

    def save(self, job: AnalysisJob) -> None:
        self.saved.append(job)

    def get(self, project_id: str, analysis_id: str) -> AnalysisJob:
        for job in reversed(self.saved):
            if (job.project_id, job.analysis_id) == (project_id, analysis_id):
                return job
        raise RecordNotFound(f"no analysis {analysis_id!r} in project {project_id!r}")


class _Pipeline:
    """Stands in for `AnalyzeScript` / `EvaluateDelta` at the one method
    `StartAnalysis` calls, recording its arguments and the state of the last
    stored job at the moment it ran."""

    def __init__(self, jobs: _JobStore | None = None, error: BaseException | None = None) -> None:
        self._jobs = jobs
        self._error = error
        self.calls: list[tuple[Any, ...]] = []
        self.states_when_called: list[AnalysisState] = []

    def execute(
        self,
        project_id: str,
        script_id: str,
        version: int,
        gcs_uri: str,
        jurisdiction: Jurisdiction,
        at: str,
    ) -> AnalysisReport:
        self.calls.append((project_id, script_id, version, gcs_uri, jurisdiction, at))
        if self._jobs is not None and self._jobs.saved:
            self.states_when_called.append(self._jobs.saved[-1].state)
        if self._error is not None:
            raise self._error
        return AnalysisReport(
            script=Script(
                script_id=script_id,
                project_id=project_id,
                version=version,
                gcs_uri=gcs_uri,
                jurisdiction_code=jurisdiction.code,
                scenes=[],
            ),
            findings=(),
            tracker_items=(),
        )


class _SyncRunner:
    """Runs the work inline, so the background path lands on the test's thread."""

    def __init__(self) -> None:
        self.script_ids: list[str] = []

    def __call__(self, script_id: str, work: Work) -> None:
        self.script_ids.append(script_id)
        work()


class _DeferredRunner:
    """Takes the work and never runs it, so a test can read the store the way
    a poll arriving before the thread starts would."""

    def __init__(self) -> None:
        self.work: Work | None = None

    def __call__(self, script_id: str, work: Work) -> None:
        self.work = work


def _use_case(
    jobs: _JobStore,
    analyze: _Pipeline | None = None,
    delta: _Pipeline | None = None,
    clock: _Clock | None = None,
    runner: Runner | None = None,
) -> StartAnalysis:
    return StartAnalysis(
        jobs,
        cast(AnalyzeScript, analyze if analyze is not None else _Pipeline()),
        cast(EvaluateDelta, delta if delta is not None else _Pipeline()),
        clock=clock if clock is not None else _Clock(),
        runner=runner if runner is not None else _SyncRunner(),
    )


# Bound to their contracts by annotated assignment (CP-012, D3): the store to
# its port, and the shipped default to the `Runner` alias, which is what
# catches a runner signature that drifts from what `composition.py` supplies.
_jobs_conforms: AnalysisJobStore = _JobStore()
_runner_conforms: Runner = run_in_background
_sync_runner_conforms: Runner = _SyncRunner()


def test_the_job_store_fake_satisfies_its_port() -> None:
    assert isinstance(_jobs_conforms, AnalysisJobStore)


def test_utc_now_is_timezone_aware_and_utc() -> None:
    # Asserts nothing about the value, only that the default clock carries a
    # UTC offset -- `AnalysisJob.is_stale` subtracts against it, and naive
    # minus aware raises.
    assert utc_now().utcoffset() == timedelta(0)


def test_execute_returns_a_queued_job_at_version_one() -> None:
    jobs = _JobStore()
    use_case = _use_case(jobs, runner=_DeferredRunner())

    job = use_case.execute("proj-1", "ana-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO)

    assert job.state is AnalysisState.QUEUED
    assert job.version == 1
    assert (job.project_id, job.analysis_id, job.script_id) == ("proj-1", "ana-1", "scr-1")
    assert job.created_at == job.updated_at == _START
    assert job.error == ""


def test_the_queued_row_is_already_stored_when_execute_returns() -> None:
    # A poll that lands before the thread starts has to find a row, not the
    # 404 that would read as "no such analysis" (ADR 0013).
    jobs = _JobStore()
    runner = _DeferredRunner()
    use_case = _use_case(jobs, runner=runner)

    job = use_case.execute("proj-1", "ana-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO)

    assert runner.work is not None
    assert jobs.get("proj-1", "ana-1") == job


def test_a_completed_run_leaves_the_job_succeeded_at_version_three() -> None:
    jobs = _JobStore()
    use_case = _use_case(jobs)

    use_case.execute("proj-1", "ana-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO)

    states = [job.state for job in jobs.saved]
    assert states == [AnalysisState.QUEUED, AnalysisState.RUNNING, AnalysisState.SUCCEEDED]
    final = jobs.get("proj-1", "ana-1")
    assert final.version == 3
    assert final.error == ""


def test_the_running_row_is_written_before_the_pipeline_runs() -> None:
    jobs = _JobStore()
    analyze = _Pipeline(jobs=jobs)
    use_case = _use_case(jobs, analyze=analyze)

    use_case.execute("proj-1", "ana-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO)

    assert analyze.states_when_called == [AnalysisState.RUNNING]


def test_the_pipeline_receives_the_jobs_ids_and_a_preformatted_timestamp() -> None:
    jobs = _JobStore()
    analyze = _Pipeline()
    use_case = _use_case(jobs, analyze=analyze)

    use_case.execute("proj-1", "ana-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO)

    project_id, script_id, version, gcs_uri, jurisdiction, at = analyze.calls[0]
    assert (project_id, script_id, version) == ("proj-1", "scr-1", 1)
    assert (gcs_uri, jurisdiction) == ("gs://bucket/v1.pdf", _MEXICO)
    # The format `TrackerItem.updated_at` carries, not a `datetime` repr:
    # the pipeline writes this string straight onto tracker rows. Third read
    # of the one-minute clock, after the queued and running rows.
    assert at == "2026-09-05T12:02:00Z"


def test_the_runner_is_handed_the_runs_script_id() -> None:
    # `composition.py` opens the root trace span inside its runner, and the
    # script id is what labels it.
    jobs = _JobStore()
    runner = _SyncRunner()
    use_case = _use_case(jobs, runner=runner)

    use_case.execute("proj-1", "ana-1", "scr-9", 1, "gs://bucket/v1.pdf", _MEXICO)

    assert runner.script_ids == ["scr-9"]


def test_version_one_runs_analyze_and_not_delta() -> None:
    jobs = _JobStore()
    analyze, delta = _Pipeline(), _Pipeline()
    use_case = _use_case(jobs, analyze=analyze, delta=delta)

    use_case.execute("proj-1", "ana-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO)

    assert len(analyze.calls) == 1
    assert delta.calls == []


def test_a_later_version_runs_delta_and_not_analyze() -> None:
    jobs = _JobStore()
    analyze, delta = _Pipeline(), _Pipeline()
    use_case = _use_case(jobs, analyze=analyze, delta=delta)

    use_case.execute("proj-1", "ana-1", "scr-2", 2, "gs://bucket/v2.pdf", _MEXICO)

    assert len(delta.calls) == 1
    assert analyze.calls == []


def test_a_raising_pipeline_leaves_the_job_failed_without_raising_to_the_caller() -> None:
    # Nothing is left to raise to: the request that queued this job answered
    # 202 minutes ago, and the FAILED row is the report.
    jobs = _JobStore()
    analyze = _Pipeline(error=RuntimeError("Document AI returned no pages"))
    use_case = _use_case(jobs, analyze=analyze)

    use_case.execute("proj-1", "ana-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO)

    final = jobs.get("proj-1", "ana-1")
    assert final.state is AnalysisState.FAILED
    assert final.error == "analysis failed; retry or contact project support"
    assert final.version == 3


def test_a_pipeline_raising_with_a_blank_message_still_produces_a_non_empty_error() -> None:
    # `AnalysisJob.failed` refuses a blank reason, so a bare `raise
    # SomeError()` would take the failure write down with it and leave the
    # row stuck in RUNNING until the reaper found it.
    jobs = _JobStore()
    analyze = _Pipeline(error=RuntimeError("   "))
    use_case = _use_case(jobs, analyze=analyze)

    use_case.execute("proj-1", "ana-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO)

    final = jobs.get("proj-1", "ana-1")
    assert final.state is AnalysisState.FAILED
    assert final.error == "analysis failed; retry or contact project support"


def test_a_keyboard_interrupt_is_not_recorded_as_an_analysis_failure() -> None:
    # `except Exception` does not cover `BaseException` on purpose: an
    # instance being shut down is not a bad script, and a FAILED row would
    # tell the producer it was.
    jobs = _JobStore()
    analyze = _Pipeline(error=KeyboardInterrupt())
    use_case = _use_case(jobs, analyze=analyze)

    with pytest.raises(KeyboardInterrupt):
        use_case.execute("proj-1", "ana-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO)

    assert [job.state for job in jobs.saved] == [AnalysisState.QUEUED, AnalysisState.RUNNING]


def test_the_shipped_runner_runs_the_work_on_a_thread_that_finishes() -> None:
    # The one test that exercises `run_in_background` itself. It waits on an
    # Event rather than sleeping, so it takes as long as the thread does.
    ran: list[str] = []
    done = threading.Event()

    def work() -> None:
        ran.append("work")
        done.set()

    run_in_background("scr-1", work)

    assert done.wait(timeout=5), "the background work never ran"
    assert ran == ["work"]
