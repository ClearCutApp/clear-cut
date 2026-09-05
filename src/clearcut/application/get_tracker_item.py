"""Reads one tracker item at its newest version (docs/api/openapi.yaml,
`GET /api/projects/{project_id}/tracker-items/{item_id}`).

A pass-through to `TrackerStore.latest`, and it exists rather than the route
holding the port because `adapters/http/routes.py` takes use-case instances
and nothing else (CHECKPOINTS.md Decision D30). `ListTrackerItems` is the
same shape for the list side of the same table.

Both ids are required. An item id is unique only inside its project --
`EVT-001` exists in every project that ever ran an analysis -- so a read on
the id alone resolves to whichever row a background merge happened to keep
(ADR 0014). The project scoping lives on the port, and this use case passes
both through rather than defaulting either.
"""

from clearcut.application.ports import TrackerStore
from clearcut.domain.tracker import TrackerItem


class GetTrackerItem:
    """`GetTrackerItem(tracker)`."""

    def __init__(self, tracker: TrackerStore) -> None:
        self._tracker = tracker

    def execute(self, project_id: str, item_id: str) -> TrackerItem:
        """The item's newest version.

        `RecordNotFound` propagates for an id the project does not hold; the
        route turns it into the contract's 404.
        """
        return self._tracker.latest(project_id, item_id)
