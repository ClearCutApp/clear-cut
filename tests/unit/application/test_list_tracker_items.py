"""Unit tests for `ListTrackerItems` (CP-029, docs/plan/sdd.md Section 4.2,
`GET /api/tracker?project_id=`).

`adapters/http/routes.py` may hold use-case instances only, never a port
directly (CHECKPOINTS.md Decision D30 -- "CP-029's factory takes use-case
instances and nothing else"), so the tracker-listing read that route needs
gets the same one-collaborator, one-`execute` shape as every other use case
(AGENT.md Section 2 rule 5) instead of the route holding `TrackerStore`.

Hand-written fake for the one port (AGENT.md Section 5) -- no
`unittest.mock`, no network.
"""

from clearcut.application.list_tracker_items import ListTrackerItems
from clearcut.application.ports import TrackerStore
from clearcut.domain.script import Script
from clearcut.domain.tracker import TrackerItem, TrackerState


def _item(item_id: str, project_id: str) -> TrackerItem:
    return TrackerItem(
        item_id=item_id,
        project_id=project_id,
        finding_id="EVT-001",
        scene_numbers=(1,),
        state=TrackerState.BLOCKED,
        required_document="Sync License",
        contact="rights@example.com",
        litigation_posture="none on record",
        note="",
        updated_at="2026-08-30T00:00:00Z",
        version=1,
    )


class FakeTrackerStore:
    """`latest_for_project` is the only method this use case calls; the
    other four raise if reached, so a mistaken extra call fails loudly."""

    def __init__(self, items: list[TrackerItem]) -> None:
        self._items = items

    def save(self, items: list[TrackerItem]) -> None:
        raise NotImplementedError

    def latest(self, item_id: str) -> TrackerItem:
        raise NotImplementedError

    def latest_for_project(self, project_id: str) -> list[TrackerItem]:
        return [item for item in self._items if item.project_id == project_id]

    def record_script(self, script: Script) -> None:
        raise NotImplementedError

    def latest_script(self, project_id: str) -> Script | None:
        raise NotImplementedError


_conforms: TrackerStore = FakeTrackerStore([])


def test_fake_tracker_store_satisfies_the_trackerstore_port() -> None:
    assert isinstance(_conforms, TrackerStore)


def test_execute_returns_only_the_named_projects_items() -> None:
    items = [_item("itm-1", "proj-1"), _item("itm-2", "proj-2")]
    use_case = ListTrackerItems(FakeTrackerStore(items))

    result = use_case.execute("proj-1")

    assert result == [items[0]]


def test_execute_returns_an_empty_list_for_a_project_with_no_rows() -> None:
    use_case = ListTrackerItems(FakeTrackerStore([]))

    assert use_case.execute("proj-1") == []


class _PositionalOnlyTrackerStore:
    """Parameter name differs from `TrackerStore`'s, so a keyword call fails."""

    def __init__(self, items: list[TrackerItem]) -> None:
        self._items = items

    def save(self, a: list[TrackerItem]) -> None:
        raise NotImplementedError

    def latest(self, a: str) -> TrackerItem:
        raise NotImplementedError

    def latest_for_project(self, a: str) -> list[TrackerItem]:
        return self._items

    def record_script(self, a: Script) -> None:
        raise NotImplementedError

    def latest_script(self, a: str) -> Script | None:
        raise NotImplementedError


def test_execute_calls_latest_for_project_positionally() -> None:
    """D15: a keyword call through this fake raises `TypeError`."""
    items = [_item("itm-1", "proj-1")]
    use_case = ListTrackerItems(_PositionalOnlyTrackerStore(items))

    assert use_case.execute("proj-1") == items
