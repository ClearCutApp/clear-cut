"""Unit tests for the ClickHouse-backed TrackerStore adapter (CP-023).

The real `clickhouse_connect.driver.client.Client` opens an HTTPS connection
at construction, so these tests fake the client boundary directly (AGENT.md
Section 5): `FakeChClient` is a hand-written stand-in for the three methods
this adapter actually calls (`command`, `insert`, `query`), recording every
call it received. No network, no `unittest.mock`, no live ClickHouse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from clearcut.adapters.clickhouse.client import ClickHouseUnavailable
from clearcut.adapters.clickhouse.tracker import (
    ClickHouseTrackerStore,
    TrackerItemNotFound,
    _script_to_row,
    _tracker_item_to_row,
)
from clearcut.application.ports import TrackerStore
from clearcut.domain.script import Scene, Script
from clearcut.domain.tracker import TrackerItem, TrackerState
from tests.unit.conftest import install_in_memory_telemetry, metric_attributes_by_name


@dataclass
class _FakeQueryResult:
    """Stands in for `clickhouse_connect.driver.query.QueryResult`, whose
    `result_rows` attribute is the only part this adapter reads."""

    result_rows: list[tuple[Any, ...]] = field(default_factory=list)


class FakeChClient:
    """Records every `command`, `insert`, and `query` call it receives, and
    returns a canned `_FakeQueryResult` set by the test via `set_result`."""

    def __init__(self) -> None:
        self.commands: list[str] = []
        self.inserts: list[tuple[str, list[list[Any]], list[str]]] = []
        self.queries: list[tuple[str, dict[str, Any] | None]] = []
        self._next_result = _FakeQueryResult()

    def set_result(self, rows: list[tuple[Any, ...]]) -> None:
        self._next_result = _FakeQueryResult(result_rows=rows)

    def command(self, cmd: str) -> str:
        self.commands.append(cmd)
        return "ok"

    def insert(self, table: str, data: list[list[Any]], column_names: list[str]) -> None:
        self.inserts.append((table, data, column_names))

    def query(self, query: str, parameters: dict[str, Any] | None = None) -> _FakeQueryResult:
        self.queries.append((query, parameters))
        return self._next_result


class ExplodingChClient:
    """Raises a real `clickhouse_connect` driver error on every call."""

    def command(self, cmd: str) -> str:
        from clickhouse_connect.driver.exceptions import DatabaseError

        raise DatabaseError("simulated ClickHouse failure")

    def insert(self, table: str, data: list[list[Any]], column_names: list[str]) -> None:
        from clickhouse_connect.driver.exceptions import DatabaseError

        raise DatabaseError("simulated ClickHouse failure")

    def query(self, query: str, parameters: dict[str, Any] | None = None) -> _FakeQueryResult:
        from clickhouse_connect.driver.exceptions import DatabaseError

        raise DatabaseError("simulated ClickHouse failure")


def _item(
    item_id: str = "EVT-001",
    project_id: str = "proj-a",
    version: int = 1,
    state: TrackerState = TrackerState.BLOCKED,
    scene_numbers: tuple[int, ...] = (1,),
    needs_review: bool = False,
    draft_email: str | None = None,
) -> TrackerItem:
    return TrackerItem(
        item_id=item_id,
        project_id=project_id,
        finding_id="EVT-001",
        scene_numbers=scene_numbers,
        state=state,
        required_document="release form",
        contact="rights@example.com",
        litigation_posture="none on record",
        note="",
        updated_at="2026-08-30T00:00:00Z",
        version=version,
        needs_review=needs_review,
        draft_email=draft_email,
    )


def _script(project_id: str = "proj-a", version: int = 1, script_id: str = "script-1") -> Script:
    scenes = [
        Scene(number=1, heading="INT. HOUSE - DAY", page_start=1, page_end=1, text="Rex barks."),
        Scene(
            number=2, heading="EXT. STREET - DAY", page_start=2, page_end=2, text="Cut to street."
        ),
    ]
    return Script(
        script_id=script_id,
        project_id=project_id,
        version=version,
        gcs_uri="gs://bucket/script.pdf",
        jurisdiction_code="US",
        scenes=scenes,
    )


def test_adapter_satisfies_the_trackerstore_port() -> None:
    adapter = ClickHouseTrackerStore(FakeChClient())
    checked: TrackerStore = adapter
    assert isinstance(checked, TrackerStore)


def test_ensure_schema_emits_tracker_items_as_replacingmergetree_keyed_on_item_id() -> None:
    client = FakeChClient()
    adapter = ClickHouseTrackerStore(client)

    adapter.ensure_schema()

    tracker_ddl = next(cmd for cmd in client.commands if "tracker_items" in cmd)
    assert "ReplacingMergeTree(version)" in tracker_ddl
    assert "ORDER BY item_id" in tracker_ddl


def test_ensure_schema_emits_script_versions_as_replacingmergetree() -> None:
    client = FakeChClient()
    adapter = ClickHouseTrackerStore(client)

    adapter.ensure_schema()

    script_ddl = next(cmd for cmd in client.commands if "script_versions" in cmd)
    assert "ReplacingMergeTree(version)" in script_ddl


def test_save_inserts_one_row_per_item_carrying_its_version() -> None:
    client = FakeChClient()
    adapter = ClickHouseTrackerStore(client)
    items = [_item(item_id="EVT-001", version=1), _item(item_id="EVT-002", version=3)]

    adapter.save(items)

    assert len(client.inserts) == 1
    table, rows, columns = client.inserts[0]
    assert table == "tracker_items"
    assert len(rows) == 2
    version_index = columns.index("version")
    assert {row[version_index] for row in rows} == {1, 3}


def test_save_never_issues_a_command_only_an_insert() -> None:
    client = FakeChClient()
    adapter = ClickHouseTrackerStore(client)

    adapter.save([_item()])

    assert client.commands == []


def test_latest_for_project_returns_the_highest_version_per_item_id_in_unhelpful_order() -> None:
    client = FakeChClient()
    adapter = ClickHouseTrackerStore(client)
    first_seen = _item(item_id="EVT-001", version=1, state=TrackerState.BLOCKED)
    highest = _item(item_id="EVT-001", version=3, state=TrackerState.CLEARED)
    last_seen = _item(item_id="EVT-001", version=2, state=TrackerState.IN_PROGRESS)
    other = _item(item_id="EVT-002", version=1, state=TrackerState.IN_PROGRESS)
    # Deliberately unhelpful order: for EVT-001, the highest version (3) sits
    # in the middle -- neither "first row wins" nor "last row wins" would
    # find it, only a real per-item max-version comparison does.
    client.set_result(
        [
            tuple(_tracker_item_to_row(first_seen)),
            tuple(_tracker_item_to_row(highest)),
            tuple(_tracker_item_to_row(last_seen)),
            tuple(_tracker_item_to_row(other)),
        ]
    )

    result = adapter.latest_for_project("proj-a")

    assert len(result) == 2
    by_id = {item.item_id: item for item in result}
    assert by_id["EVT-001"].version == 3
    assert by_id["EVT-001"].state == TrackerState.CLEARED
    assert by_id["EVT-002"].version == 1


def test_latest_for_project_excludes_rows_belonging_to_another_project() -> None:
    client = FakeChClient()
    adapter = ClickHouseTrackerStore(client)
    in_project_a = _item(item_id="EVT-001", project_id="proj-a", version=1)
    # Higher version than anything in proj-a, so a naive highest-version-wins
    # read that ignores project_id would surface it as proj-a's answer too.
    in_project_b = _item(item_id="EVT-002", project_id="proj-b", version=9)
    client.set_result(
        [tuple(_tracker_item_to_row(in_project_a)), tuple(_tracker_item_to_row(in_project_b))]
    )

    result = adapter.latest_for_project("proj-a")

    assert [item.item_id for item in result] == ["EVT-001"]
    assert all(item.project_id == "proj-a" for item in result)


def test_latest_for_project_returns_empty_list_for_a_project_with_no_rows() -> None:
    client = FakeChClient()
    adapter = ClickHouseTrackerStore(client)
    other_project_item = _item(item_id="EVT-001", project_id="proj-b", version=1)
    client.set_result([tuple(_tracker_item_to_row(other_project_item))])

    result = adapter.latest_for_project("proj-a")

    assert result == []


def test_ensure_schema_emits_tracker_items_with_a_project_id_column() -> None:
    client = FakeChClient()
    adapter = ClickHouseTrackerStore(client)

    adapter.ensure_schema()

    tracker_ddl = next(cmd for cmd in client.commands if "tracker_items" in cmd)
    assert "project_id String" in tracker_ddl


def test_save_writes_the_items_own_project_id_not_a_default() -> None:
    client = FakeChClient()
    adapter = ClickHouseTrackerStore(client)

    adapter.save([_item(project_id="proj-b")])

    _, rows, columns = client.inserts[0]
    project_index = columns.index("project_id")
    assert rows[0][project_index] == "proj-b"


def test_record_script_and_latest_script_round_trip_scenes_and_hashes() -> None:
    client = FakeChClient()
    adapter = ClickHouseTrackerStore(client)
    script = _script(project_id="proj-a")

    adapter.record_script(script)
    _, rows, _ = client.inserts[0]
    client.set_result([tuple(rows[0])])

    result = adapter.latest_script("proj-a")

    assert result == script
    assert [scene.content_hash for scene in result.scenes] == [
        scene.content_hash for scene in script.scenes
    ]


def test_latest_script_returns_none_for_a_project_with_no_stored_version() -> None:
    client = FakeChClient()
    adapter = ClickHouseTrackerStore(client)

    result = adapter.latest_script("no-such-project")

    assert result is None


def test_latest_returns_the_stored_item_at_its_highest_version() -> None:
    client = FakeChClient()
    adapter = ClickHouseTrackerStore(client)
    stale = _item(item_id="EVT-001", version=1, state=TrackerState.BLOCKED)
    fresh = _item(item_id="EVT-001", version=2, state=TrackerState.CLEARED)
    client.set_result([tuple(_tracker_item_to_row(stale)), tuple(_tracker_item_to_row(fresh))])

    result = adapter.latest("EVT-001")

    assert result.version == 2
    assert result.state == TrackerState.CLEARED


def test_latest_filters_by_item_id_before_selecting_the_highest_version() -> None:
    client = FakeChClient()
    adapter = ClickHouseTrackerStore(client)
    target = _item(item_id="EVT-001", version=1, state=TrackerState.BLOCKED)
    # A foreign item with a higher version than the target's only row: if
    # `latest` picked the highest version across all returned rows instead
    # of filtering to `item_id` first, it would return this row instead.
    foreign = _item(item_id="EVT-002", version=9, state=TrackerState.CLEARED)
    client.set_result([tuple(_tracker_item_to_row(target)), tuple(_tracker_item_to_row(foreign))])

    result = adapter.latest("EVT-001")

    assert result.item_id == "EVT-001"
    assert result.version == 1


def test_latest_round_trips_needs_review_draft_email_and_scene_numbers() -> None:
    client = FakeChClient()
    adapter = ClickHouseTrackerStore(client)
    item = _item(
        project_id="proj-a",
        scene_numbers=(3, 7),
        needs_review=True,
        draft_email="rights@example.com",
    )
    client.set_result([tuple(_tracker_item_to_row(item))])

    result = adapter.latest("EVT-001")

    assert result.needs_review is True
    assert result.draft_email == "rights@example.com"
    assert result.project_id == "proj-a"
    assert result.scene_numbers == (3, 7)


def test_latest_script_returns_the_highest_version_per_project_in_unhelpful_order() -> None:
    client = FakeChClient()
    adapter = ClickHouseTrackerStore(client)
    first_seen = _script(project_id="proj-a", version=1)
    highest = _script(project_id="proj-a", version=3)
    last_seen = _script(project_id="proj-a", version=2)
    # Deliberately unhelpful order: the highest version (3) sits in the
    # middle, so neither "first row wins" nor "last row wins" would find it,
    # only a real max-version comparison does.
    client.set_result(
        [
            tuple(_script_to_row(first_seen)),
            tuple(_script_to_row(highest)),
            tuple(_script_to_row(last_seen)),
        ]
    )

    result = adapter.latest_script("proj-a")

    assert result == highest
    assert result is not None
    assert result.version == 3


def test_ensure_schema_wraps_a_client_error_as_tracker_unavailable() -> None:
    adapter = ClickHouseTrackerStore(ExplodingChClient())

    with pytest.raises(ClickHouseUnavailable):
        adapter.ensure_schema()


def test_latest_raises_not_found_naming_the_id_for_an_unknown_item() -> None:
    client = FakeChClient()
    adapter = ClickHouseTrackerStore(client)
    client.set_result([])

    with pytest.raises(TrackerItemNotFound) as excinfo:
        adapter.latest("missing-item")

    assert "missing-item" in str(excinfo.value)


def test_save_wraps_a_client_error_as_tracker_unavailable() -> None:
    adapter = ClickHouseTrackerStore(ExplodingChClient())

    with pytest.raises(ClickHouseUnavailable):
        adapter.save([_item()])


def test_latest_wraps_a_client_error_as_tracker_unavailable() -> None:
    adapter = ClickHouseTrackerStore(ExplodingChClient())

    with pytest.raises(ClickHouseUnavailable):
        adapter.latest("EVT-001")


def test_record_script_wraps_a_client_error_as_tracker_unavailable() -> None:
    adapter = ClickHouseTrackerStore(ExplodingChClient())

    with pytest.raises(ClickHouseUnavailable):
        adapter.record_script(_script())


def test_latest_script_wraps_a_client_error_as_tracker_unavailable() -> None:
    adapter = ClickHouseTrackerStore(ExplodingChClient())

    with pytest.raises(ClickHouseUnavailable):
        adapter.latest_script("proj-a")


# ---------------------------------------------------------------------------
# CP-031 (ADR 0008, SDD Section 6): `save` opens a "track" span, records
# `clearcut_stage_latency_ms` with stage="track", and refreshes
# `clearcut_tracker_items` by state (CP-031 review, BLOCKING 2).
# ---------------------------------------------------------------------------


def test_save_opens_a_track_span_records_stage_latency_and_refreshes_the_gauge(
    isolated_otel: None,
) -> None:
    span_exporter, metric_reader = install_in_memory_telemetry()
    client = FakeChClient()
    adapter = ClickHouseTrackerStore(client)
    items = [_item(item_id="EVT-001", state=TrackerState.BLOCKED)]

    adapter.save(items)

    spans = [span for span in span_exporter.get_finished_spans() if span.name == "track"]
    assert len(spans) == 1

    points_by_name = metric_attributes_by_name(metric_reader)
    latency_points = points_by_name["clearcut_stage_latency_ms"]
    assert latency_points
    assert all(point["stage"] == "track" for point in latency_points)

    gauge_points = points_by_name["clearcut_tracker_items"]
    assert gauge_points
    assert any(point["state"] == TrackerState.BLOCKED.value for point in gauge_points)
