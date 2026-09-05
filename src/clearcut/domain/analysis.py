"""AnalysisJob, one run of the clearance pipeline over one script version.

A script upload answers 202 and hands back an analysis id, so the browser
polls this row rather than holding a request open for the minutes Document AI
and Gemini take. Every transition writes a new versioned row instead of
mutating the old one, the same latest-wins read `TrackerItem` relies on.

`created_at` and `updated_at` are timezone-aware `datetime` values, not the
preformatted strings `TrackerItem.updated_at` carries. `is_stale` compares
`updated_at` against a caller-supplied `now`, and a string cannot be compared
without reparsing it first, which would put a date format in the domain. Both
`datetime` and `timedelta` are stdlib, so the domain rule that this layer
imports nothing third-party still holds (AGENT.md Section 2). Adapters format
on the way out.

No I/O and no clock read: the time each transition is recorded at arrives as
an argument.
"""

import enum
from dataclasses import dataclass, replace
from datetime import datetime, timedelta


class AnalysisState(enum.StrEnum):
    """Where one analysis run stands. SUCCEEDED and FAILED are terminal."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


_TERMINAL_STATES = frozenset({AnalysisState.SUCCEEDED, AnalysisState.FAILED})


@dataclass(frozen=True)
class AnalysisJob:
    """One background analysis of one script version (SDD Section 4.1)."""

    analysis_id: str
    project_id: str
    script_id: str
    state: AnalysisState
    created_at: datetime
    updated_at: datetime
    error: str = ""
    version: int = 1

    def __post_init__(self) -> None:
        if not self.analysis_id.strip():
            raise ValueError("analysis_id must not be blank")
        if not self.project_id.strip():
            raise ValueError("project_id must not be blank")
        if not self.script_id.strip():
            raise ValueError("script_id must not be blank")
        if self.version < 1:
            raise ValueError(f"version must be >= 1, got {self.version}")

    def running(self, at: datetime) -> "AnalysisJob":
        """A new job in RUNNING at `version + 1`; the receiver is untouched."""
        self._refuse_when_finished("running")
        return replace(self, state=AnalysisState.RUNNING, updated_at=at, version=self.version + 1)

    def succeeded(self, at: datetime) -> "AnalysisJob":
        """A new job in SUCCEEDED at `version + 1`; the receiver is untouched."""
        self._refuse_when_finished("succeeded")
        return replace(self, state=AnalysisState.SUCCEEDED, updated_at=at, version=self.version + 1)

    def failed(self, reason: str, at: datetime) -> "AnalysisJob":
        """A new job in FAILED carrying `reason` as `error`, at `version + 1`.

        A blank or whitespace-only reason raises `ValueError`: a failure with
        no reason records nothing a missing row would not also look like, and
        the browser polling this job has nothing to show the producer.
        """
        self._refuse_when_finished("failed")
        if not reason.strip():
            raise ValueError("failure reason must not be blank")
        return replace(
            self,
            state=AnalysisState.FAILED,
            error=reason,
            updated_at=at,
            version=self.version + 1,
        )

    def _refuse_when_finished(self, transition: str) -> None:
        """Raises when the job already reached SUCCEEDED or FAILED.

        `TrackerItem` accepts every ordered pair of states because each one
        records a producer action. These states record work that has already
        finished, so re-entering one would claim a run happened that did not.
        """
        if self.state in _TERMINAL_STATES:
            raise ValueError(f"{self.state.value} is terminal; cannot apply {transition}")

    def is_stale(self, now: datetime, after: timedelta) -> bool:
        """Whether this job has been RUNNING for longer than `after`.

        A Cloud Run instance reclaimed mid-run leaves its row in RUNNING with
        nothing left to write the failure, so a read reaps the job instead:
        the poll that finds it stale is what turns it into a FAILED the
        producer can see. Exactly `after` is not yet stale.
        """
        return self.state is AnalysisState.RUNNING and now - self.updated_at > after
