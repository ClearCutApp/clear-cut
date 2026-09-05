"""Transitions one tracker item and triggers its actions (docs/plan/sdd.md
Section 4.2; docs/plan/agentic-workflow.md Section 5).

Scoped to three of SDD Section 4.2's four actions: a state transition, the
outreach `DraftEmail` action, and `Notify`. `generate_document` needs another
model call and its own port; `stakeholder_link` needs a `RightsResearch`
result this use case has no way to ask for. Both are deferred.

The versioned-row rule (SDD Section 2) has one owner, `TrackerItem`: every
change it accepts returns a new instance at `version + 1`. This module never
computes a version itself and never calls `dataclasses.replace` -- a second
site that bumps versions is a second owner the day that rule gains a field
(CHECKPOINTS.md Decision D22).

`DraftEmail` only ever drafts: the system never sends what it writes. The
producer reviews it on the dashboard and sends it themselves; only that human
action, a separate `Transition`, moves the item from BLOCKED to IN_PROGRESS
(docs/plan/agentic-workflow.md Section 5).
"""

from dataclasses import dataclass

from clearcut.application.ports import Notifier, TrackerStore
from clearcut.domain.tracker import TrackerItem, TrackerState


@dataclass(frozen=True)
class Transition:
    """Move the item to `state`
    (`PATCH /api/projects/{project_id}/tracker-items/{item_id}`)."""

    state: TrackerState


@dataclass(frozen=True)
class DraftEmail:
    """Draft an outreach email from the item's own resolved data."""


@dataclass(frozen=True)
class Notify:
    """Notify the producer over the webhook; the item is not changed."""

    reason: str


Action = Transition | DraftEmail | Notify


def _draft_email_text(item: TrackerItem) -> str:
    """The outreach template filled from the finding's data already resolved
    onto `item` (contact and required document, from `RightsResearch`)."""
    return (
        f"Subject: Rights clearance request -- {item.required_document}\n\n"
        f"To: {item.contact}\n\n"
        f"We are requesting rights clearance for: {item.required_document} "
        f"(finding {item.finding_id}). Litigation posture on file: "
        f"{item.litigation_posture or 'none on record'}."
    )


def _apply(item: TrackerItem, action: Transition | DraftEmail, at: str) -> TrackerItem:
    if isinstance(action, Transition):
        return item.transitioned_to(action.state, at)
    return item.with_draft_email(_draft_email_text(item), at)


class ResolveFinding:
    """`ResolveFinding(tracker, notifier)` (docs/plan/sdd.md Section 4.2)."""

    def __init__(self, tracker: TrackerStore, notifier: Notifier) -> None:
        self._tracker = tracker
        self._notifier = notifier

    def execute(self, project_id: str, item_id: str, action: Action, at: str) -> TrackerItem:
        item = self._tracker.latest(project_id, item_id)
        if isinstance(action, Notify):
            self._notifier.notify(item, action.reason)
            return item
        updated = _apply(item, action, at)
        self._tracker.save([updated])
        return updated
