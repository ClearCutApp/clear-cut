"""Persists tracker items and script versions over ClickHouse (docs/plan/sdd.md
Section 3, docs/plan/infrastructure.md Section 6).

`tracker_items` is a `ReplacingMergeTree` keyed on `item_id` and versioned by
each row's `version` column, matching `TrackerItem`'s own frozen, versioned
design (`domain/tracker.py`): every state transition is a new row, never a
mutation, so the table's latest-wins read always resolves to the last
producer action. `script_versions` follows the same shape, keyed on
`project_id`, so `latest_script` resolves to the newest uploaded version
without a live schema read.

`TrackerItem` carries its own `project_id` (CP-036, `.claude/CHECKPOINTS.md`
Decision D24) rather than `TrackerStore.save` taking one as a parameter --
`ResolveFinding` is item-scoped and has no project to hand it, so the item
that already knows its project is the one that writes the column.
`latest_for_project` filters on that column with a `WHERE` clause, the same
shape `latest_script` already used for `script_versions`.

Constructor parameters are typed against a narrow local `Protocol`
(`_ChClient`) covering only the three `clickhouse_connect` client methods
this adapter calls, rather than the concrete `Client` class -- the same
pattern `BigQueryLoreStore` uses, so a hand-written unit-test fake never
needs to open a real HTTPS connection (AGENT.md Section 5).
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from clearcut.domain.script import Scene, Script
from clearcut.domain.tracker import TrackerItem, TrackerState

_TRACKER_ITEMS_DDL = """\
CREATE TABLE IF NOT EXISTS tracker_items (
    item_id String,
    project_id String,
    finding_id String,
    scene_numbers Array(UInt32),
    state String,
    needs_review UInt8,
    required_document String,
    contact String,
    litigation_posture String,
    draft_email Nullable(String),
    note String,
    updated_at String,
    version UInt32
) ENGINE = ReplacingMergeTree(version)
ORDER BY item_id
"""

_SCRIPT_VERSIONS_DDL = """\
CREATE TABLE IF NOT EXISTS script_versions (
    script_id String,
    project_id String,
    version UInt32,
    gcs_uri String,
    jurisdiction_code String,
    scenes String
) ENGINE = ReplacingMergeTree(version)
ORDER BY project_id
"""

_TRACKER_COLUMNS = [
    "item_id",
    "project_id",
    "finding_id",
    "scene_numbers",
    "state",
    "needs_review",
    "required_document",
    "contact",
    "litigation_posture",
    "draft_email",
    "note",
    "updated_at",
    "version",
]

_SCRIPT_COLUMNS = [
    "script_id",
    "project_id",
    "version",
    "gcs_uri",
    "jurisdiction_code",
    "scenes",
]


class TrackerUnavailable(Exception):
    """The ClickHouse client failed to execute a command, insert, or query."""


class TrackerItemNotFound(Exception):
    """No stored row exists for the requested `item_id`."""

    def __init__(self, item_id: str) -> None:
        super().__init__(f"no tracker item found for item_id={item_id!r}")
        self.item_id = item_id


class _QueryResult(Protocol):
    """The subset of `clickhouse_connect.driver.query.QueryResult` this
    adapter reads."""

    result_rows: list[tuple[Any, ...]]


class _ChClient(Protocol):
    """The subset of `clickhouse_connect.driver.client.Client` this adapter
    calls."""

    def command(self, cmd: str) -> object: ...

    def insert(self, table: str, data: list[list[Any]], column_names: list[str]) -> object: ...

    def query(self, query: str, parameters: dict[str, Any] | None = None) -> _QueryResult: ...


class ClickHouseTrackerStore:
    """Implements `TrackerStore` over a ClickHouse Cloud HTTPS connection."""

    def __init__(self, client: _ChClient) -> None:
        self._client = client

    def ensure_schema(self) -> None:
        try:
            self._client.command(_TRACKER_ITEMS_DDL)
            self._client.command(_SCRIPT_VERSIONS_DDL)
        except Exception as exc:
            raise TrackerUnavailable(f"failed to create tables: {exc}") from exc

    def save(self, items: list[TrackerItem]) -> None:
        rows = [_tracker_item_to_row(item) for item in items]
        try:
            self._client.insert("tracker_items", rows, _TRACKER_COLUMNS)
        except Exception as exc:
            raise TrackerUnavailable(f"failed to save {len(items)} item(s): {exc}") from exc

    def latest(self, item_id: str) -> TrackerItem:
        query = "SELECT * FROM tracker_items WHERE item_id = {item_id:String}"
        rows = self._query_tracker_rows(query, {"item_id": item_id})
        matching = [row for row in rows if row[0] == item_id]
        if not matching:
            raise TrackerItemNotFound(item_id)
        latest_row = max(matching, key=lambda row: row[_TRACKER_COLUMNS.index("version")])
        return _row_to_tracker_item(latest_row)

    def latest_for_project(self, project_id: str) -> list[TrackerItem]:
        query = "SELECT * FROM tracker_items WHERE project_id = {project_id:String}"
        rows = self._query_tracker_rows(query, {"project_id": project_id})
        project_index = _TRACKER_COLUMNS.index("project_id")
        matching = [row for row in rows if row[project_index] == project_id]
        latest_by_item_id: dict[str, tuple[Any, ...]] = {}
        version_index = _TRACKER_COLUMNS.index("version")
        for row in matching:
            item_id = row[0]
            current = latest_by_item_id.get(item_id)
            if current is None or row[version_index] > current[version_index]:
                latest_by_item_id[item_id] = row
        return [_row_to_tracker_item(row) for _item_id, row in sorted(latest_by_item_id.items())]

    def record_script(self, script: Script) -> None:
        row = _script_to_row(script)
        try:
            self._client.insert("script_versions", [row], _SCRIPT_COLUMNS)
        except Exception as exc:
            raise TrackerUnavailable(
                f"failed to record script {script.script_id!r}: {exc}"
            ) from exc

    def latest_script(self, project_id: str) -> Script | None:
        try:
            result = self._client.query(
                "SELECT * FROM script_versions WHERE project_id = {project_id:String}",
                {"project_id": project_id},
            )
        except Exception as exc:
            raise TrackerUnavailable(
                f"failed to read latest script for project {project_id!r}: {exc}"
            ) from exc
        rows = list(result.result_rows)
        if not rows:
            return None
        version_index = _SCRIPT_COLUMNS.index("version")
        latest_row = max(rows, key=lambda row: row[version_index])
        return _row_to_script(latest_row)

    def _query_tracker_rows(
        self, query: str, parameters: dict[str, Any] | None
    ) -> list[tuple[Any, ...]]:
        try:
            result = self._client.query(query, parameters)
        except Exception as exc:
            raise TrackerUnavailable(f"failed to query tracker_items: {exc}") from exc
        return list(result.result_rows)


def _tracker_item_to_row(item: TrackerItem) -> list[Any]:
    return [
        item.item_id,
        item.project_id,
        item.finding_id,
        list(item.scene_numbers),
        item.state.value,
        int(item.needs_review),
        item.required_document,
        item.contact,
        item.litigation_posture,
        item.draft_email,
        item.note,
        item.updated_at,
        item.version,
    ]


def _row_to_tracker_item(row: tuple[Any, ...]) -> TrackerItem:
    values = dict(zip(_TRACKER_COLUMNS, row, strict=True))
    return TrackerItem(
        item_id=values["item_id"],
        project_id=values["project_id"],
        finding_id=values["finding_id"],
        scene_numbers=tuple(int(n) for n in values["scene_numbers"]),
        state=TrackerState(values["state"]),
        needs_review=bool(values["needs_review"]),
        required_document=values["required_document"],
        contact=values["contact"],
        litigation_posture=values["litigation_posture"],
        draft_email=values["draft_email"],
        note=values["note"],
        updated_at=values["updated_at"],
        version=int(values["version"]),
    )


def _script_to_row(script: Script) -> list[Any]:
    scenes = [
        {
            "number": scene.number,
            "heading": scene.heading,
            "page_start": scene.page_start,
            "page_end": scene.page_end,
            "text": scene.text,
        }
        for scene in script.scenes
    ]
    return [
        script.script_id,
        script.project_id,
        script.version,
        script.gcs_uri,
        script.jurisdiction_code,
        json.dumps(scenes),
    ]


def _row_to_script(row: tuple[Any, ...]) -> Script:
    values = dict(zip(_SCRIPT_COLUMNS, row, strict=True))
    scenes = [
        Scene(
            number=raw["number"],
            heading=raw["heading"],
            page_start=raw["page_start"],
            page_end=raw["page_end"],
            text=raw["text"],
        )
        for raw in json.loads(values["scenes"])
    ]
    return Script(
        script_id=values["script_id"],
        project_id=values["project_id"],
        version=int(values["version"]),
        gcs_uri=values["gcs_uri"],
        jurisdiction_code=values["jurisdiction_code"],
        scenes=scenes,
    )
