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
    poster_uri: str | None = None,
    format: str | None = None,
    status: str | None = None,
) -> Project:
    return Project(
        project_id=project_id,
        title=title,
        jurisdiction_code=jurisdiction_code,
        created_at=created_at,
        poster_uri=poster_uri,
        format=format,
        status=status,
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


# --- The three optional presentation fields ---------------------------------
#
# They are `Nullable(String)` columns added after rows already existed, so both
# directions matter: a project that carries them must survive the round trip,
# and a row written before they existed must still read.


def test_a_project_with_every_optional_field_survives_the_round_trip() -> None:
    client = FakeChClient()
    adapter = ClickHouseProjectStore(client)
    stored = _project(
        poster_uri="gs://clearcut-posters/prj-4f2a.jpg",
        format="feature_film",
        status="in_development",
    )

    adapter.save(stored)
    table, rows, columns = client.inserts[0]
    client.set_result([tuple(rows[0])])

    assert adapter.get("prj-4f2a") == stored
    assert rows[0][columns.index("poster_uri")] == "gs://clearcut-posters/prj-4f2a.jpg"
    assert rows[0][columns.index("format")] == "feature_film"
    assert rows[0][columns.index("status")] == "in_development"


def test_a_project_with_none_of_them_writes_three_nulls() -> None:
    """Not empty strings. The column is `Nullable(String)`, and a row that
    stored `''` would come back as a format the domain then refuses."""
    client = FakeChClient()

    ClickHouseProjectStore(client).save(_project())

    _, rows, columns = client.inserts[0]
    for column in ("poster_uri", "format", "status"):
        assert rows[0][columns.index(column)] is None, column


def test_a_row_written_before_the_columns_existed_still_reads() -> None:
    """`SELECT *` against a table nobody has widened yet answers with the
    original four values. Reading those as an unset poster is the truth about
    that row; refusing to read it would take the whole list down."""
    client = FakeChClient()
    adapter = ClickHouseProjectStore(client)
    client.set_result([("prj-4f2a", "El Ultimo Verano", "AR", "2026-09-05T12:00:00Z")])

    project = adapter.get("prj-4f2a")

    assert (project.poster_uri, project.format, project.status) == (None, None, None)
    assert project.title == "El Ultimo Verano"


def test_an_empty_string_read_back_folds_into_unset() -> None:
    """A driver that prefers `''` to `None` for a nullable column must not
    hand the domain a format it is bound to refuse."""
    client = FakeChClient()
    adapter = ClickHouseProjectStore(client)
    client.set_result([("prj-4f2a", "El Ultimo Verano", "AR", "2026-09-05T12:00:00Z", "", "", "")])

    project = adapter.get("prj-4f2a")

    assert (project.poster_uri, project.format, project.status) == (None, None, None)


def test_the_insert_names_every_column_the_create_statement_declares() -> None:
    """The insert passes column names explicitly, so a column added to the DDL
    and forgotten here would write `NULL` into it forever without failing."""
    from clearcut.adapters.clickhouse import schema

    client = FakeChClient()
    ClickHouseProjectStore(client).save(_project())

    _, _, columns = client.inserts[0]
    ddl = next(cmd for cmd in schema.DDL if cmd.startswith("CREATE TABLE IF NOT EXISTS projects"))
    for column in columns:
        assert f"{column} " in ddl or f"`{column}` " in ddl, column
