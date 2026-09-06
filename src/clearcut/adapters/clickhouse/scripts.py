"""Persists script versions over ClickHouse (ADR 0014, `application/ports.py`).

This module owns the `script_versions` row mapping. `tracker.py` imports it
rather than keeping a second copy, because `TrackerStore.record_script` and
`latest_script` write and read the same table: `EvaluateDelta` still calls
them, and moving that half of the tracker port is a separate migration. Two
copies of the mapping would let the delta path and the REST surface disagree
about the JSON shape of a scene, and the disagreement would surface as a
missing highlight rather than as an error.

Scenes cross the boundary as a JSON string in one `String` column rather than
as a nested ClickHouse type. `Scene.content_hash` is derived on construction
from the text, so it is not written: a stored hash and a stored text that
disagree would be a second source of truth for the identity the delta path
joins on.
"""

from __future__ import annotations

import json
from typing import Any

from clearcut.adapters.clickhouse import client as ch_client
from clearcut.adapters.clickhouse import schema
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.script import Scene, Script

SCRIPT_COLUMNS = [
    "script_id",
    "project_id",
    "version",
    "gcs_uri",
    "jurisdiction_code",
    "scenes",
]


class ScriptNotFound(RecordNotFound):
    """No stored row exists for the requested project and `script_id`."""

    def __init__(self, project_id: str, script_id: str) -> None:
        super().__init__(f"no script found for project_id={project_id!r} script_id={script_id!r}")
        self.project_id = project_id
        self.script_id = script_id


class ClickHouseScriptStore:
    """Implements `ScriptStore` over a ClickHouse Cloud HTTPS connection."""

    def __init__(self, client: ch_client._ChClient) -> None:
        self._client = client

    def ensure_schema(self) -> None:
        schema.ensure_schema(self._client)

    def save(self, script: Script) -> None:
        try:
            self._client.insert("script_versions", [script_to_row(script)], SCRIPT_COLUMNS)
        except Exception as exc:
            raise ch_client.ClickHouseUnavailable(
                f"failed to save script {script.script_id!r}: {exc}"
            ) from exc

    def get(self, project_id: str, script_id: str) -> Script:
        rows = self._query(
            "SELECT * FROM script_versions "
            "WHERE project_id = {project_id:String} AND script_id = {script_id:String}",
            {"project_id": project_id, "script_id": script_id},
        )
        scripts = [
            script
            for script in (row_to_script(row) for row in rows)
            if script.project_id == project_id and script.script_id == script_id
        ]
        if not scripts:
            raise ScriptNotFound(project_id, script_id)
        return scripts[0]

    def for_project(self, project_id: str) -> list[Script]:
        rows = self._query(
            "SELECT * FROM script_versions WHERE project_id = {project_id:String}",
            {"project_id": project_id},
        )
        scripts = [
            script
            for script in (row_to_script(row) for row in rows)
            if script.project_id == project_id
        ]
        return sorted(scripts, key=lambda script: script.version)

    def latest(self, project_id: str) -> Script | None:
        versions = self.for_project(project_id)
        return versions[-1] if versions else None

    def _query(self, query: str, parameters: dict[str, Any] | None) -> list[tuple[Any, ...]]:
        try:
            result = self._client.query(query, parameters)
        except Exception as exc:
            raise ch_client.ClickHouseUnavailable(
                f"failed to query script_versions: {exc}"
            ) from exc
        return list(result.result_rows)


def script_to_row(script: Script) -> list[Any]:
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


def row_to_script(row: tuple[Any, ...]) -> Script:
    values = dict(zip(SCRIPT_COLUMNS, row, strict=True))
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
