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
from typing import Any

from clearcut.application.notification_ports import ProjectNotifications
from clearcut.application.ports import Notifier, TrackerStore
from clearcut.application.tracker_mutations import TrackerMutations
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.tracker import ClearanceDetails, TrackerConflict, TrackerItem, TrackerState
from clearcut.domain.workspace import InvalidWorkspace


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


@dataclass(frozen=True)
class EditDetails:
    details: ClearanceDetails


Action = Transition | DraftEmail | Notify | EditDetails


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


def _apply(
    item: TrackerItem, action: Transition | DraftEmail | EditDetails, at: str
) -> TrackerItem:
    if isinstance(action, Transition):
        return item.transitioned_to(action.state, at)
    if isinstance(action, EditDetails):
        return item.with_details(action.details, at)
    return item.with_draft_email(_draft_email_text(item), at)


class ResolveFinding:
    """`ResolveFinding(tracker, notifier)` (docs/plan/sdd.md Section 4.2)."""

    def __init__(
        self,
        tracker: TrackerStore,
        notifier: Notifier,
        mutations: TrackerMutations | None = None,
        notifications: ProjectNotifications | None = None,
    ) -> None:
        self._tracker = tracker
        self._notifier = notifier
        self._mutations = mutations
        self._notifications = notifications

    def execute(
        self,
        project_id: str,
        item_id: str,
        action: Action,
        at: str,
        *,
        expected_version: int | None = None,
        actor: str = "demo",
    ) -> TrackerItem:
        item = self._tracker.latest(project_id, item_id)
        if isinstance(action, Notify):
            if not isinstance(action.reason, str) or not 1 <= len(action.reason.strip()) <= 2000:
                raise InvalidWorkspace("notification reason must contain 1–2000 characters")
            if self._notifications is not None:
                self._notifications.record(item, actor, action.reason, at)
            else:
                self._notifier.notify(item, action.reason)
            return item
        if expected_version is not None and item.version != expected_version:
            raise TrackerConflict(item.version)
        updated = _apply(item, action, at)
        if self._mutations is not None:
            self._mutations.compare_save(updated, item.version, actor)
        else:
            self._tracker.save([updated])
        return updated

    def history(
        self, project_id: str, item_id: str, before_version: int | None = None
    ) -> list[dict[str, Any]]:
        if self._mutations is None:
            raise SourceUnavailable("clearance audit unavailable")
        return self._mutations.history(project_id, item_id, before_version)
