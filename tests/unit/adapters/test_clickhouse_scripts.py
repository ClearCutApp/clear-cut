"""Unit tests for the ClickHouse-backed `ScriptStore` (ADR 0014).

This store reads and writes the same `script_versions` table
`TrackerStore.record_script` / `latest_script` still use. It owns the row
mapping both share, and adds the reads the REST surface needs: one version by
id, every version of a project, and the newest one.
"""

from __future__ import annotations

import pytest

from clearcut.adapters.clickhouse.client import ClickHouseUnavailable
from clearcut.adapters.clickhouse.scripts import (
    ClickHouseScriptStore,
    ScriptNotFound,
    script_to_row,
)
from clearcut.application.ports import ScriptStore
from clearcut.domain.script import Scene, Script
from tests.unit.adapters.fake_ch_client import ExplodingChClient, FakeChClient


def _script(project_id: str = "prj-a", script_id: str = "scr-1", version: int = 1) -> Script:
    return Script(
        script_id=script_id,
        project_id=project_id,
        version=version,
        gcs_uri=f"gs://clearcut-scripts/{project_id}/{script_id}.pdf",
        jurisdiction_code="AR",
        scenes=[
            Scene(
                number=1,
                heading="INT. BAR NOTTURNO - NIGHT",
                page_start=1,
                page_end=2,
                text=f"draft {version}",
            ),
            Scene(
                number=4,
                heading="EXT. CALLE CORRIENTES - DAY",
                page_start=3,
                page_end=3,
                text="Mariana walks north.",
            ),
        ],
    )


def test_adapter_satisfies_the_scriptstore_port() -> None:
    adapter = ClickHouseScriptStore(FakeChClient())
    checked: ScriptStore = adapter
    assert isinstance(checked, ScriptStore)


def test_save_inserts_one_row_into_script_versions() -> None:
    client = FakeChClient()

    ClickHouseScriptStore(client).save(_script())

    table, rows, columns = client.inserts[0]
    assert table == "script_versions"
    assert rows[0][columns.index("script_id")] == "scr-1"
    assert rows[0][columns.index("version")] == 1


def test_get_round_trips_the_scenes_and_their_content_hashes() -> None:
    """The scenes cross the boundary as a JSON string, so a hash rebuilt on
    read has to match the one the domain computed on write -- that is the
    identity the delta path joins on."""
    client = FakeChClient()
    adapter = ClickHouseScriptStore(client)
    script = _script()
    client.set_result([tuple(script_to_row(script))])

    result = adapter.get("prj-a", "scr-1")

    assert result == script
    assert [scene.content_hash for scene in result.scenes] == [
        scene.content_hash for scene in script.scenes
    ]


def test_get_ignores_a_row_from_another_project_with_the_same_script_id() -> None:
    client = FakeChClient()
    adapter = ClickHouseScriptStore(client)
    client.set_result([tuple(script_to_row(_script(project_id="prj-b", script_id="scr-1")))])

    with pytest.raises(ScriptNotFound):
        adapter.get("prj-a", "scr-1")


def test_get_raises_not_found_naming_both_ids() -> None:
    client = FakeChClient()
    adapter = ClickHouseScriptStore(client)
    client.set_result([])

    with pytest.raises(ScriptNotFound) as excinfo:
        adapter.get("prj-a", "scr-missing")

    assert "scr-missing" in str(excinfo.value)
    assert "prj-a" in str(excinfo.value)


def test_for_project_returns_every_version_ordered_oldest_first() -> None:
    """The bug ADR 0014 closes, on the read side: before the re-key one row
    survived per project, so this list could only ever have one entry."""
    client = FakeChClient()
    adapter = ClickHouseScriptStore(client)
    client.set_result(
        [
            tuple(script_to_row(_script(script_id="scr-2", version=2))),
            tuple(script_to_row(_script(script_id="scr-1", version=1))),
            tuple(script_to_row(_script(script_id="scr-3", version=3))),
        ]
    )

    assert [script.version for script in adapter.for_project("prj-a")] == [1, 2, 3]


def test_for_project_excludes_another_projects_versions() -> None:
    client = FakeChClient()
    adapter = ClickHouseScriptStore(client)
    client.set_result(
        [
            tuple(script_to_row(_script(project_id="prj-a", script_id="scr-1", version=1))),
            tuple(script_to_row(_script(project_id="prj-b", script_id="scr-9", version=9))),
        ]
    )

    assert [script.script_id for script in adapter.for_project("prj-a")] == ["scr-1"]


def test_latest_returns_the_highest_version_in_unhelpful_order() -> None:
    client = FakeChClient()
    adapter = ClickHouseScriptStore(client)
    highest = _script(script_id="scr-3", version=3)
    # The highest version sits in the middle, so neither "first row wins" nor
    # "last row wins" finds it -- only a real max-version comparison does.
    client.set_result(
        [
            tuple(script_to_row(_script(script_id="scr-1", version=1))),
            tuple(script_to_row(highest)),
            tuple(script_to_row(_script(script_id="scr-2", version=2))),
        ]
    )

    assert adapter.latest("prj-a") == highest


def test_latest_returns_none_for_a_project_with_no_stored_version() -> None:
    client = FakeChClient()
    client.set_result([])

    assert ClickHouseScriptStore(client).latest("prj-empty") is None


def test_save_wraps_a_client_error_as_clickhouse_unavailable() -> None:
    with pytest.raises(ClickHouseUnavailable):
        ClickHouseScriptStore(ExplodingChClient()).save(_script())


def test_get_wraps_a_client_error_as_clickhouse_unavailable() -> None:
    with pytest.raises(ClickHouseUnavailable):
        ClickHouseScriptStore(ExplodingChClient()).get("prj-a", "scr-1")


def test_for_project_wraps_a_client_error_as_clickhouse_unavailable() -> None:
    with pytest.raises(ClickHouseUnavailable):
        ClickHouseScriptStore(ExplodingChClient()).for_project("prj-a")


def test_latest_wraps_a_client_error_as_clickhouse_unavailable() -> None:
    with pytest.raises(ClickHouseUnavailable):
        ClickHouseScriptStore(ExplodingChClient()).latest("prj-a")
