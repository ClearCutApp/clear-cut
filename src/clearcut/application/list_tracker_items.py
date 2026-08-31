"""Lists the tracker items for one project (docs/plan/sdd.md Section 4.2,
`GET /api/tracker?project_id=`).

One collaborator and one public entry point, the same shape every use case
here has (AGENT.md Section 2 rule 5). It exists so `adapters/http/routes.py`
can take a use-case instance for this route instead of holding `TrackerStore`
itself -- CP-029's factory takes use-case instances and nothing else
(CHECKPOINTS.md Decision D30).
"""

from clearcut.application.ports import TrackerStore
from clearcut.domain.tracker import TrackerItem


class ListTrackerItems:
    """`ListTrackerItems(tracker)`."""

    def __init__(self, tracker: TrackerStore) -> None:
        self._tracker = tracker

    def execute(self, project_id: str) -> list[TrackerItem]:
        return self._tracker.latest_for_project(project_id)
