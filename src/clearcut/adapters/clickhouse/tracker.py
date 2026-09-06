"""Persists tracker items and script versions over ClickHouse (docs/plan/sdd.md
Section 3, docs/plan/infrastructure.md Section 6).

The DDL and the client protocol this store depends on live in
`schema.py` and `client.py` respectively (CP-062) -- this module holds only
the store itself, so a sibling store (a future `scripts.py` or `projects.py`)
can share both without importing this one.

`TrackerItem` carries its own `project_id` (CP-036, `.claude/CHECKPOINTS.md`
Decision D24) rather than `TrackerStore.save` taking one as a parameter --
`ResolveFinding` is item-scoped and has no project to hand it, so the item
that already knows its project is the one that writes the column.
`latest_for_project` filters on that column with a `WHERE` clause, the same
shape `latest_script` already used for `script_versions`.

`record_script` and `latest_script` read and write the table `scripts.py`
owns, and borrow that module's row mapping rather than keeping a second copy.
`EvaluateDelta` still calls them, so moving this half of the port onto
`ScriptStore` is its own migration (ADR 0014); until then both stores have to
agree byte for byte about the JSON a scene is stored as.
"""

from __future__ import annotations

import time
from collections import Counter
from typing import Any

from opentelemetry import metrics, trace

from clearcut.adapters.clickhouse import client as ch_client
from clearcut.adapters.clickhouse import schema, scripts
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.script import Script
from clearcut.domain.tracker import TrackerItem, TrackerState


def _record_stage(stage: str, start: float) -> None:
    """CP-031 (ADR 0008, SDD Section 6); see `adapters/gcp/document_ai.py`
    for why the tracer/meter lookups happen fresh on every call."""
    duration_ms = (time.perf_counter() - start) * 1000
    metrics.get_meter(__name__).create_histogram(
        "clearcut_stage_latency_ms", unit="ms", description="Pipeline stage latency"
    ).record(duration_ms, {"stage": stage})


def _refresh_tracker_items_gauge(items: list[TrackerItem]) -> None:
    """`clearcut_tracker_items`, refreshed on every tracker write (SDD
    Section 6): the gauge is set, not accumulated, to the count of items
    this write touched per state -- the same write `save` just made durable."""
    gauge = metrics.get_meter(__name__).create_gauge(
        "clearcut_tracker_items", description="Tracker items by state, refreshed on every write"
    )
    counts = Counter(item.state.value for item in items)
    for state, count in counts.items():
        gauge.set(count, {"state": state})


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


class TrackerItemNotFound(RecordNotFound):
    """No stored row exists for the requested project and `item_id`.

    Both ids are in the message because either one alone is ambiguous: the
    same `EVT-001` exists in every project that ran an analysis, so "no
    tracker item EVT-001" reads as a bug in the id rather than a read against
    the wrong project (ADR 0014).
    """

    def __init__(self, project_id: str, item_id: str) -> None:
        super().__init__(f"no tracker item found for project_id={project_id!r} item_id={item_id!r}")
        self.project_id = project_id
        self.item_id = item_id


class ClickHouseTrackerStore:
    """Implements `TrackerStore` over a ClickHouse Cloud HTTPS connection."""

    def __init__(self, client: ch_client._ChClient) -> None:
        self._client = client

    def ensure_schema(self) -> None:
        schema.ensure_schema(self._client)

    def save(self, items: list[TrackerItem]) -> None:
        stage_start = time.perf_counter()
        with trace.get_tracer(__name__).start_as_current_span("track"):
            rows = [_tracker_item_to_row(item) for item in items]
            try:
                self._client.insert("tracker_items", rows, _TRACKER_COLUMNS)
            except Exception as exc:
                raise ch_client.ClickHouseUnavailable(
                    f"failed to save {len(items)} item(s): {exc}"
                ) from exc
        _record_stage("track", stage_start)
        _refresh_tracker_items_gauge(items)

    def latest(self, project_id: str, item_id: str) -> TrackerItem:
        query = (
            "SELECT * FROM tracker_items "
            "WHERE project_id = {project_id:String} AND item_id = {item_id:String}"
        )
        rows = self._query_tracker_rows(query, {"project_id": project_id, "item_id": item_id})
        project_index = _TRACKER_COLUMNS.index("project_id")
        matching = [row for row in rows if row[0] == item_id and row[project_index] == project_id]
        if not matching:
            raise TrackerItemNotFound(project_id, item_id)
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
        row = scripts.script_to_row(script)
        try:
            self._client.insert("script_versions", [row], scripts.SCRIPT_COLUMNS)
        except Exception as exc:
            raise ch_client.ClickHouseUnavailable(
                f"failed to record script {script.script_id!r}: {exc}"
            ) from exc

    def latest_script(self, project_id: str) -> Script | None:
        try:
            result = self._client.query(
                "SELECT * FROM script_versions WHERE project_id = {project_id:String}",
                {"project_id": project_id},
            )
        except Exception as exc:
            raise ch_client.ClickHouseUnavailable(
                f"failed to read latest script for project {project_id!r}: {exc}"
            ) from exc
        rows = list(result.result_rows)
        if not rows:
            return None
        version_index = scripts.SCRIPT_COLUMNS.index("version")
        latest_row = max(rows, key=lambda row: row[version_index])
        return scripts.row_to_script(latest_row)

    def _query_tracker_rows(
        self, query: str, parameters: dict[str, Any] | None
    ) -> list[tuple[Any, ...]]:
        try:
            result = self._client.query(query, parameters)
        except Exception as exc:
            raise ch_client.ClickHouseUnavailable(f"failed to query tracker_items: {exc}") from exc
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
