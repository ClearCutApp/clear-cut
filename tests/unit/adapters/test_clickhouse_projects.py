"""Unit tests for the ClickHouse-backed `ProjectStore` (ADR 0014).

`GET /api/projects` is the first screen the SPA draws, so the project list is
a read of its own rather than something derived from whichever tracker rows a
project happens to own.
"""

from __future__ import annotations

import pytest

from clearcut.adapters.clickhouse.client import ClickHouseUnavailable
from clearcut.adapters.clickhouse.projects import (
    ClickHouseProjectStore,
    ProjectNotFound,
    _project_to_row,
)
from clearcut.application.ports import ProjectStore
from clearcut.domain.project import Project
from tests.unit.adapters.fake_ch_client import ExplodingChClient, FakeChClient


def _project(
    project_id: str = "prj-4f2a",
    title: str = "El Ultimo Verano",
    jurisdiction_code: str = "AR",
    created_at: str = "2026-09-05T12:00:00Z",
) -> Project:
    return Project(
        project_id=project_id,
        title=title,
        jurisdiction_code=jurisdiction_code,
        created_at=created_at,
    )


def test_adapter_satisfies_the_projectstore_port() -> None:
    adapter = ClickHouseProjectStore(FakeChClient())
    checked: ProjectStore = adapter
    assert isinstance(checked, ProjectStore)


def test_ensure_schema_keys_projects_on_the_project_id() -> None:
    client = FakeChClient()

    ClickHouseProjectStore(client).ensure_schema()

    ddl = next(cmd for cmd in client.commands if "CREATE TABLE IF NOT EXISTS projects" in cmd)
    assert "ORDER BY project_id" in ddl


def test_save_inserts_one_row_into_projects() -> None:
    client = FakeChClient()

    ClickHouseProjectStore(client).save(_project())

    assert len(client.inserts) == 1
    table, rows, columns = client.inserts[0]
    assert table == "projects"
    assert rows[0][columns.index("title")] == "El Ultimo Verano"
    assert rows[0][columns.index("jurisdiction_code")] == "AR"


def test_get_returns_the_stored_project() -> None:
    client = FakeChClient()
    adapter = ClickHouseProjectStore(client)
    stored = _project(title="La Ciudad Sin Nombre")
    client.set_result([tuple(_project_to_row(stored))])

    assert adapter.get("prj-4f2a") == stored


def test_get_ignores_a_row_belonging_to_another_project() -> None:
    """The read filters in Python as well as in SQL, the same belt-and-braces
    `latest_for_project` uses: a widened `WHERE` clause is a one-character
    edit away from returning somebody else's project."""
    client = FakeChClient()
    adapter = ClickHouseProjectStore(client)
    client.set_result([tuple(_project_to_row(_project(project_id="prj-other")))])

    with pytest.raises(ProjectNotFound):
        adapter.get("prj-4f2a")


def test_get_raises_not_found_naming_the_id() -> None:
    client = FakeChClient()
    adapter = ClickHouseProjectStore(client)
    client.set_result([])

    with pytest.raises(ProjectNotFound) as excinfo:
        adapter.get("prj-missing")

    assert "prj-missing" in str(excinfo.value)


def test_all_returns_every_stored_project_ordered_by_id() -> None:
    client = FakeChClient()
    adapter = ClickHouseProjectStore(client)
    second = _project(project_id="prj-b", title="Segundo")
    first = _project(project_id="prj-a", title="Primero")
    client.set_result([tuple(_project_to_row(second)), tuple(_project_to_row(first))])

    assert [project.project_id for project in adapter.all()] == ["prj-a", "prj-b"]


def test_all_returns_an_empty_list_when_nothing_is_stored() -> None:
    client = FakeChClient()
    client.set_result([])

    assert ClickHouseProjectStore(client).all() == []


def test_ensure_schema_wraps_a_client_error_as_clickhouse_unavailable() -> None:
    with pytest.raises(ClickHouseUnavailable):
        ClickHouseProjectStore(ExplodingChClient()).ensure_schema()


def test_save_wraps_a_client_error_as_clickhouse_unavailable() -> None:
    with pytest.raises(ClickHouseUnavailable):
        ClickHouseProjectStore(ExplodingChClient()).save(_project())


def test_get_wraps_a_client_error_as_clickhouse_unavailable() -> None:
    with pytest.raises(ClickHouseUnavailable):
        ClickHouseProjectStore(ExplodingChClient()).get("prj-4f2a")


def test_all_wraps_a_client_error_as_clickhouse_unavailable() -> None:
    with pytest.raises(ClickHouseUnavailable):
        ClickHouseProjectStore(ExplodingChClient()).all()
