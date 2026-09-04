"""TrackerItem, the actionable side of a Finding (docs/plan/sdd.md Section 2).

Every state transition writes a new versioned row rather than mutating the
old one, so ClickHouse's latest-wins read always resolves to the last action
a producer took. No I/O, no third-party imports, stdlib only; the time each
transition is recorded at arrives as an argument.
"""

import enum
from collections.abc import Iterable
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

    def noted(self, text: str, at: str) -> "TrackerItem":
        """A new item carrying `text` as `note` at `version + 1`; `state` is
        unchanged.

        ADR 0007 / SDD Section 4.3: a scene removed between two script
        versions is neither cleared away nor forgotten -- its tracker item
        stays open with a note recording why, because a cut scene can return
        in a later version. A blank or whitespace-only note raises
        `ValueError` rather than writing a version that stores nothing an
        unwritten note would also look like.
        """
        if not text.strip():
            raise ValueError("note text must not be blank")
        return replace(self, note=text, updated_at=at, version=self.version + 1)

    def flagged_and_noted(self, note: str, at: str) -> "TrackerItem":
        """A new item with `needs_review=True` and `note` set to `note`, at
        `version + 1`; `state` is unchanged.

        ADR 0007 (D37): an asset that moves to a different scene leaves the
        item tied to its old scene open, flagged for a producer to look at
        again, and carrying a note naming the scene it was cleared against --
        one tracker write, not two, so version history records one event for
        one change.
        """
        return replace(self, needs_review=True, note=note, updated_at=at, version=self.version + 1)

    def with_draft_email(self, text: str, at: str) -> "TrackerItem":
        """A new item carrying `text` as `draft_email` at `version + 1`.

        `state` is unchanged: drafting outreach is not a state transition on
        its own (docs/plan/agentic-workflow.md Section 5 — a human approves
        before the item moves BLOCKED to IN_PROGRESS). A blank or
        whitespace-only draft raises `ValueError` rather than writing a
        version that stores nothing an unwritten draft would also look like.
        """
        if not text.strip():
            raise ValueError("draft_email text must not be blank")
        return replace(self, draft_email=text, updated_at=at, version=self.version + 1)


_NEEDS_REVIEW_WEIGHT = 50


@dataclass(frozen=True, slots=True)
class ClearanceRollup:
    """A count of tracker items per bucket, and the clearance percent they imply.

    An item flagged `needs_review` counts in `needs_review` regardless of its
    `state`: it is the bucket a producer must look at next, not a fifth
    dimension layered on top of the other three.
    """

    blocked: int
    in_progress: int
    cleared: int
    needs_review: int

    @property
    def total(self) -> int:
        return self.blocked + self.in_progress + self.cleared + self.needs_review

    @property
    def clearance_percent(self) -> int:
        """The weighted average of BLOCKED=0, IN_PROGRESS=50, CLEARED=100 and
        NEEDS_REVIEW=50, rounded half up to an int. 0 when there are no items.
        """
        if self.total == 0:
            return 0
        weighted = (
            self.in_progress * 50 + self.cleared * 100 + self.needs_review * _NEEDS_REVIEW_WEIGHT
        )
        return (2 * weighted + self.total) // (2 * self.total)


def clearance_rollup(items: Iterable[TrackerItem]) -> ClearanceRollup:
    """Bucket `items` into blocked / in_progress / cleared / needs_review counts.

    An item flagged `needs_review` is counted there ahead of its `state`.
    """
    blocked = in_progress = cleared = needs_review = 0
    for item in items:
        if item.needs_review:
            needs_review += 1
        elif item.state is TrackerState.BLOCKED:
            blocked += 1
        elif item.state is TrackerState.IN_PROGRESS:
            in_progress += 1
        else:
            cleared += 1
    return ClearanceRollup(
        blocked=blocked, in_progress=in_progress, cleared=cleared, needs_review=needs_review
    )
