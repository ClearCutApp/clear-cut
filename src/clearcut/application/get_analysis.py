"""Reads one analysis job, and reaps it when the run behind it is gone
(ADR 0013).

This is the read the browser polls after `POST .../scripts` answers 202. Most
calls are a plain load. The one rule it holds is the reaper: a Cloud Run
instance reclaimed mid-run leaves its row saying RUNNING with nothing left in
the process to write the failure, so the poll that finds the row stale is what
turns it into a FAILED the producer can see. Without that, the row says
RUNNING forever and the browser spins forever.

`AnalysisJob.is_stale` is the predicate and it lives in the domain; the
deadline and the write are here, because a timeout is an operational choice
about how long a run may go quiet, not a rule about what an analysis is.
"""

from collections.abc import Callable
from datetime import datetime, timedelta

from clearcut.application.ports import AnalysisJobStore
from clearcut.application.start_analysis import utc_now
from clearcut.domain.analysis import AnalysisJob

# How long a job may sit in RUNNING without a write before a read declares it
# lost. A real run takes twelve to twenty minutes against live services (ADR
# 0013), so this is generous enough not to reap work that is merely slow.
STALE_AFTER = timedelta(minutes=30)


class GetAnalysis:
    """`GetAnalysis(jobs)` (ADR 0013).

    `stale_after` is a constructor argument rather than a read of the module
    constant so a test can prove the boundary without waiting thirty minutes.
    `clock` is injected for the same reason `StartAnalysis` injects it: a unit
    test reads no clock (AGENT.md Section 5).
    """

    def __init__(
        self,
        jobs: AnalysisJobStore,
        *,
        clock: Callable[[], datetime] = utc_now,
        stale_after: timedelta = STALE_AFTER,
    ) -> None:
        self._jobs = jobs
        self._clock = clock
        self._stale_after = stale_after

    def execute(self, project_id: str, analysis_id: str) -> AnalysisJob:
        """The job as stored, unless it is stale, in which case a FAILED one.

        An unknown `analysis_id` propagates the port's `RecordNotFound`: the
        route maps that to 404, and a poll for an analysis nobody queued is
        exactly that.

        A job that is not stale is returned without a write. Saving an
        unchanged row on every poll would bump `version` once per second per
        open browser tab, which is the versioned-row equivalent of a busy
        loop.
        """
        job = self._jobs.get(project_id, analysis_id)
        now = self._clock()
        if not job.is_stale(now, self._stale_after):
            return job
        reaped = job.failed(_timeout_reason(self._stale_after), now)
        self._jobs.save(reaped)
        return reaped


def _timeout_reason(stale_after: timedelta) -> str:
    """The `error` a reaped job carries, naming the deadline it passed."""
    minutes = stale_after.total_seconds() / 60
    return f"analysis timed out: no progress for over {minutes:g} minutes"
