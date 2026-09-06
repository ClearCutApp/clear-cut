"""Unit tests for `GetTrackerItem` (docs/api/openapi.yaml,
`GET /api/projects/{project_id}/tracker-items/{item_id}`).

`tests/unit/fakes.py` carries no `TrackerStore`, so this file writes one, keyed
on both ids the way ClickHouse's latest-wins read resolves a row (ADR 0014).
The four methods this use case never calls raise, so a mistaken extra call
fails loudly.

Hand-written fakes only, no `unittest.mock`, no network (AGENT.md Section 5).
"""

import pytest

from clearcut.application.get_tracker_item import GetTrackerItem
from clearcut.application.ports import TrackerStore
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.script import Script
from clearcut.domain.tracker import TrackerItem, TrackerState


def _item(item_id: str, project_id: str, state: TrackerState) -> TrackerItem:
    return TrackerItem(
        item_id=item_id,
        project_id=project_id,
        finding_id="EVT-001",
        scene_numbers=(1,),
        state=state,
        required_document="Sync License",
        contact="rights@example.com",
        litigation_posture="none on record",
        note="",
        updated_at="2026-09-05T00:00:00Z",
        version=1,
    )


class FakeTrackerStore:
    """`latest` is the only method this use case calls."""

    def __init__(self, items: list[TrackerItem]) -> None:
        self._items = items

    def save(self, items: list[TrackerItem]) -> None:
        raise NotImplementedError

    def latest(self, project_id: str, item_id: str) -> TrackerItem:
        for item in self._items:
            if item.project_id == project_id and item.item_id == item_id:
                return item
        raise RecordNotFound(f"no item {item_id!r} in project {project_id!r}")

    def latest_for_project(self, project_id: str) -> list[TrackerItem]:
        raise NotImplementedError

    def record_script(self, script: Script) -> None:
        raise NotImplementedError

    def latest_script(self, project_id: str) -> Script | None:
        raise NotImplementedError


_conforms: TrackerStore = FakeTrackerStore([])


def test_fake_tracker_store_satisfies_the_trackerstore_port() -> None:
    assert isinstance(_conforms, TrackerStore)


def test_execute_returns_the_item_at_its_newest_version() -> None:
    item = _item("EVT-001", "prj-4f2a", TrackerState.IN_PROGRESS)
    use_case = GetTrackerItem(FakeTrackerStore([item]))

    assert use_case.execute("prj-4f2a", "EVT-001") == item


def test_execute_resolves_the_same_item_id_independently_per_project() -> None:
    """An item id is unique only inside its project: `EVT-001` exists in every
    project that ran an analysis, so a read on the id alone would answer with
    whichever row a background merge happened to keep (ADR 0014)."""
    here = _item("EVT-001", "prj-4f2a", TrackerState.BLOCKED)
    there = _item("EVT-001", "prj-0000", TrackerState.CLEARED)
    use_case = GetTrackerItem(FakeTrackerStore([here, there]))

    assert use_case.execute("prj-4f2a", "EVT-001") is here
    assert use_case.execute("prj-0000", "EVT-001") is there


def test_execute_propagates_record_not_found_for_an_unknown_item() -> None:
    use_case = GetTrackerItem(FakeTrackerStore([]))

    with pytest.raises(RecordNotFound, match="EVT-404"):
        use_case.execute("prj-4f2a", "EVT-404")


def test_execute_propagates_record_not_found_for_an_item_in_another_project() -> None:
    item = _item("EVT-001", "prj-4f2a", TrackerState.BLOCKED)
    use_case = GetTrackerItem(FakeTrackerStore([item]))

    with pytest.raises(RecordNotFound, match="prj-0000"):
        use_case.execute("prj-0000", "EVT-001")


class _PositionalOnlyTrackerStore:
    """Parameter names differ from `TrackerStore`'s, so a keyword call fails."""

    def __init__(self, item: TrackerItem) -> None:
        self._item = item

    def save(self, a: list[TrackerItem]) -> None:
        raise NotImplementedError

    def latest(self, a: str, b: str) -> TrackerItem:
        return self._item

    def latest_for_project(self, a: str) -> list[TrackerItem]:
        raise NotImplementedError

    def record_script(self, a: Script) -> None:
        raise NotImplementedError

    def latest_script(self, a: str) -> Script | None:
        raise NotImplementedError


def test_execute_calls_latest_positionally() -> None:
    """D15: a keyword call through this fake raises `TypeError`."""
    item = _item("EVT-001", "prj-4f2a", TrackerState.BLOCKED)
    use_case = GetTrackerItem(_PositionalOnlyTrackerStore(item))

    assert use_case.execute("prj-4f2a", "EVT-001") == item
