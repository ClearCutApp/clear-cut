"""Queues one analysis and runs it off the request thread (ADR 0013).

`POST /api/projects/{project_id}/scripts` used to run the whole pipeline
inside the request. `tests/live/test_end_to_end_live.py` records
`1 passed in 870.64s` for that path, and a browser tab, a load balancer and a
phone changing networks all give up long before fourteen minutes without
telling the server. So the route answers 202 with the job this use case
returns, and the browser polls `GetAnalysis` until the state is terminal.

The job row is what the producer reads, so it is written before the work
starts: a poll that arrives while the thread is still spinning up finds a
QUEUED row rather than a 404 that would read as "no such analysis".

`AnalyzeScript.execute` and `EvaluateDelta.execute` share one signature and
one return shape, which is why the version-1-or-later branch that used to sit
in `adapters/http/routes.py` fits here as a single call site (D30).
"""

import threading
from collections.abc import Callable
from datetime import UTC, datetime

from clearcut.application.analyze_script import AnalyzeScript
from clearcut.application.evaluate_delta import EvaluateDelta
from clearcut.application.ports import AnalysisJobStore
from clearcut.domain.analysis import AnalysisJob, AnalysisState
from clearcut.domain.jurisdiction import Jurisdiction

Work = Callable[[], None]
Runner = Callable[[str, Work], None]

# The format `TrackerItem.updated_at` carries. The pipeline takes `at` as a
# preformatted string while `AnalysisJob` holds real `datetime`s (ADR 0013),
# so the two meet here and nowhere else.
_AT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def run_in_background(script_id: str, work: Work) -> None:
    """Runs `work` on a daemon thread and returns immediately.

    Daemon so a shutdown is not held open by a run nobody is waiting for;
    the job row already says RUNNING and the reaper in `GetAnalysis` turns
    it into a FAILED the producer can see.

    `script_id` labels the run for whoever supplied the runner, and this
    default ignores it.
    """
    threading.Thread(target=work, daemon=True).start()


def utc_now() -> datetime:
    """The current time, timezone-aware, in UTC."""
    return datetime.now(UTC)


def _formatted(at: datetime) -> str:
    """`at` in the string format the pipeline's `at` argument expects."""
    return at.strftime(_AT_FORMAT)


def _failure_reason(exc: BaseException) -> str:
    """A non-empty reason for `AnalysisJob.failed`, which refuses a blank one.

    A bare `raise SomeError` and a `KeyError` whose message is the missing key
    both stringify to something a producer cannot read, and `str(exc)` is
    empty outright for an exception raised with no arguments. The class name
    is the worst case, and it still names what went wrong.
    """
    return str(exc).strip() or type(exc).__name__


class StartAnalysis:
    """`StartAnalysis(jobs, analyze, delta)` (ADR 0013).

    `runner` is a plain callable with a default rather than a port, because a
    thread is not an I/O boundary: nothing leaves this process. It is this
    process deciding not to hold a request open, and AGENT.md Section 4 bans
    an interface whose only implementation stays in-process. A test passes a
    runner that calls the work inline; production passes nothing. `clock` is
    the same shape for the same reason -- a unit test reads no clock
    (AGENT.md Section 5), so the time arrives as an argument.

    A runner is handed the run's `script_id` alongside the work. The root
    trace span used to be opened in the Flask route around the pipeline call,
    which is what gave the five pipeline-stage spans one trace id; now that
    the route returns before the work starts, the span has to open inside the
    runner, and it needs the id to label it. `composition.py` supplies that
    runner, so the OpenTelemetry import stays out of this layer.
    """

    def __init__(
        self,
        jobs: AnalysisJobStore,
        analyze: AnalyzeScript,
        delta: EvaluateDelta,
        *,
        clock: Callable[[], datetime] = utc_now,
        runner: Runner = run_in_background,
    ) -> None:
        self._jobs = jobs
        self._analyze = analyze
        self._delta = delta
        self._clock = clock
        self._runner = runner

    def execute(
        self,
        project_id: str,
        analysis_id: str,
        script_id: str,
        version: int,
        gcs_uri: str,
        jurisdiction: Jurisdiction,
    ) -> AnalysisJob:
        """Saves a QUEUED job, hands the run to `runner`, and returns the job.

        The store write happens before `runner` is called: with the real
        background runner the order is racy the other way round, and the
        losing poll would 404 on an analysis the caller was just handed a
        `Location` header for.
        """
        at = self._clock()
        job = AnalysisJob(
            analysis_id=analysis_id,
            project_id=project_id,
            script_id=script_id,
            state=AnalysisState.QUEUED,
            created_at=at,
            updated_at=at,
        )
        self._jobs.save(job)
        self._runner(script_id, lambda: self._run(job, version, gcs_uri, jurisdiction))
        return job

    def _run(
        self, job: AnalysisJob, version: int, gcs_uri: str, jurisdiction: Jurisdiction
    ) -> None:
        """The whole background run: RUNNING, the pipeline, then a terminal row.

        Every exception is caught and swallowed. That is correct here and
        nowhere else in this codebase: the request that queued this job
        answered 202 minutes ago, so there is no caller left to raise to, and
        re-raising on a daemon thread only prints a traceback nobody reads.
        The FAILED row is the report -- it is what the producer's next poll
        returns.
        """
        running = job.running(self._clock())
        self._jobs.save(running)
        pipeline: AnalyzeScript | EvaluateDelta = self._analyze if version == 1 else self._delta
        try:
            pipeline.execute(
                running.project_id,
                running.script_id,
                version,
                gcs_uri,
                jurisdiction,
                _formatted(self._clock()),
            )
        except Exception as exc:
            self._jobs.save(running.failed(_failure_reason(exc), self._clock()))
        else:
            self._jobs.save(running.succeeded(self._clock()))
