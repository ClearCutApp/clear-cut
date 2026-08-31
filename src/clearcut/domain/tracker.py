"""TrackerItem, the actionable side of a Finding (docs/plan/sdd.md Section 2).

Every state transition writes a new versioned row rather than mutating the
old one, so ClickHouse's latest-wins read always resolves to the last action
a producer took. No I/O, no third-party imports, stdlib only; the time each
transition is recorded at arrives as an argument.
"""

import enum
from dataclasses import dataclass, replace


class TrackerState(enum.StrEnum):
    """Where a tracker item stands. Every ordered pair is a legal transition."""

    BLOCKED = "BLOCKED"
    IN_PROGRESS = "IN_PROGRESS"
    CLEARED = "CLEARED"


@dataclass(frozen=True)
class TrackerItem:
    """The actionable side of a Finding (SDD Section 2)."""

    item_id: str
    project_id: str
    finding_id: str
    scene_numbers: tuple[int, ...]
    state: TrackerState
    required_document: str
    contact: str
    litigation_posture: str
    note: str
    updated_at: str
    version: int
    needs_review: bool = False
    draft_email: str | None = None

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError(f"version must be >= 1, got {self.version}")
        if not self.scene_numbers:
            raise ValueError("scene_numbers must not be empty")
        if not self.project_id.strip():
            raise ValueError("project_id must not be blank")

    def transitioned_to(self, state: TrackerState, at: str) -> "TrackerItem":
        """A new item at `state` and `version + 1`; the receiver is untouched.

        Legal in both directions, including CLEARED back to BLOCKED, and even
        into the state the item already holds — every transition is an audit
        record of a producer action, not a cache of current state.
        """
        return replace(self, state=state, updated_at=at, version=self.version + 1)

    def flagged_for_review(self, at: str) -> "TrackerItem":
        """A new item with `needs_review=True` at `version + 1`; state unchanged.

        ADR 0007: a cleared item on a changed scene is neither silently kept
        nor silently dropped — it is flagged for a producer to look at again.
        """
        return replace(self, needs_review=True, updated_at=at, version=self.version + 1)
