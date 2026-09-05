"""Persists projects over ClickHouse (ADR 0014, `application/ports.py`).

`GET /api/projects` is the first screen the SPA draws. Deriving that list from
the tracker rows a project happens to own would hide a project that has been
created and never analyzed, which is every project for the minutes between
the upload and the first finding.

`projects` is a `ReplacingMergeTree` with no version column: `Project` is
immutable apart from its title, and a re-save of the same `project_id` is a
correction of that row rather than a new state to keep alongside the old one.
"""

from __future__ import annotations

from typing import Any

from clearcut.adapters.clickhouse import client as ch_client
from clearcut.adapters.clickhouse import schema
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.project import Project

PROJECT_COLUMNS = ["project_id", "title", "jurisdiction_code", "created_at"]


class ProjectNotFound(RecordNotFound):
    """No stored row exists for the requested `project_id`."""

    def __init__(self, project_id: str) -> None:
        super().__init__(f"no project found for project_id={project_id!r}")
        self.project_id = project_id


class ClickHouseProjectStore:
    """Implements `ProjectStore` over a ClickHouse Cloud HTTPS connection."""

    def __init__(self, client: ch_client._ChClient) -> None:
        self._client = client

    def ensure_schema(self) -> None:
        schema.ensure_schema(self._client)

    def save(self, project: Project) -> None:
        try:
            self._client.insert("projects", [_project_to_row(project)], PROJECT_COLUMNS)
        except Exception as exc:
            raise ch_client.ClickHouseUnavailable(
                f"failed to save project {project.project_id!r}: {exc}"
            ) from exc

    def get(self, project_id: str) -> Project:
        rows = self._query(
            "SELECT * FROM projects WHERE project_id = {project_id:String}",
            {"project_id": project_id},
        )
        matching = [row for row in rows if row[0] == project_id]
        if not matching:
            raise ProjectNotFound(project_id)
        return _row_to_project(matching[0])

    def all(self) -> list[Project]:
        rows = self._query("SELECT * FROM projects", None)
        return sorted(
            (_row_to_project(row) for row in rows), key=lambda project: project.project_id
        )

    def _query(self, query: str, parameters: dict[str, Any] | None) -> list[tuple[Any, ...]]:
        try:
            result = self._client.query(query, parameters)
        except Exception as exc:
            raise ch_client.ClickHouseUnavailable(f"failed to query projects: {exc}") from exc
        return list(result.result_rows)


def _project_to_row(project: Project) -> list[Any]:
    return [
        project.project_id,
        project.title,
        project.jurisdiction_code,
        project.created_at,
    ]


def _row_to_project(row: tuple[Any, ...]) -> Project:
    values = dict(zip(PROJECT_COLUMNS, row, strict=True))
    return Project(
        project_id=values["project_id"],
        title=values["title"],
        jurisdiction_code=values["jurisdiction_code"],
        created_at=values["created_at"],
    )
