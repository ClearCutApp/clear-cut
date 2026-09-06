"""`ClickHouseTrackerStore` against ClickHouse Cloud.

The proof is the round trip itself. `scene_numbers` is a Python tuple stored in
an `Array(UInt32)` column and `needs_review` a bool stored in `UInt8`, so an
item that comes back equal to the one that went in is an item ClickHouse
genuinely serialized, stored, and re-read. A fake returning the object it was
handed proves neither column mapping.

`ensure_schema()` runs first because nothing else creates the tables --
`composition.py` never calls it, so a live test that skips it fails on a missing
table rather than on anything meaningful.

Two tests here force a merge with `OPTIMIZE TABLE ... FINAL` instead of waiting
for one. That is the only way to observe the defect ADR 0014 closes: the old
keys lost a row during a background merge, and a fake has no merge to lose it
in.
"""

from typing import cast

import clickhouse_connect
import pytest

from clearcut.adapters.clickhouse.client import _ChClient
from clearcut.adapters.clickhouse.tracker import ClickHouseTrackerStore
from clearcut.composition import _clickhouse_host
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.script import Scene, Script
from clearcut.domain.tracker import TrackerItem, TrackerState
from tests.live.conftest import env, requires, scratch_id


def _client() -> _ChClient:
    # cast: the same widening `composition.py` documents -- `Client.query`
    # returns rows one type wider than `_ChClient` declares, true at runtime
    # and invisible to mypy structurally.
    client = cast(
        _ChClient,
        clickhouse_connect.get_client(
            # Through the same normaliser `composition.py` uses, so this test
            # accepts exactly what the console hands an operator.
            host=_clickhouse_host(env("CLICKHOUSE_HOST")),
            username=env("CLICKHOUSE_USER"),
            password=env("CLICKHOUSE_PASSWORD"),
            secure=True,
        ),
    )
    return client


def _store() -> ClickHouseTrackerStore:
    return ClickHouseTrackerStore(client=_client())


def _live_item(
    item_id: str,
    project_id: str,
    version: int = 1,
    state: TrackerState = TrackerState.BLOCKED,
) -> TrackerItem:
    return TrackerItem(
        item_id=item_id,
        project_id=project_id,
        finding_id="finding-1",
        scene_numbers=(3, 7, 11),
        state=state,
        required_document="Sync License",
        contact="rights@example.test",
        litigation_posture="none on record",
        note="",
        updated_at="2026-09-05T00:00:00Z",
        version=version,
        needs_review=True,
    )


def _live_script(project_id: str, script_id: str, version: int) -> Script:
    return Script(
        script_id=script_id,
        project_id=project_id,
        version=version,
        gcs_uri=f"gs://bucket/{script_id}.pdf",
        jurisdiction_code="AR",
        scenes=[
            Scene(
                number=1,
                heading="INT. BAR NOTTURNO - NIGHT",
                page_start=1,
                page_end=1,
                text=f"draft {version}",
            )
        ],
    )


@pytest.mark.live
@requires("CLICKHOUSE_HOST", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD")
def test_a_saved_item_survives_the_array_and_bool_column_round_trip() -> None:
    store = _store()
    store.ensure_schema()
    project_id = scratch_id("live-tracker")
    item = TrackerItem(
        item_id=scratch_id("item"),
        project_id=project_id,
        finding_id="finding-1",
        scene_numbers=(3, 7, 11),
        state=TrackerState.BLOCKED,
        required_document="Sync License",
        contact="rights@example.test",
        litigation_posture="none on record",
        note="",
        updated_at="2026-09-03T00:00:00Z",
        version=1,
        needs_review=True,
    )

    store.save([item])

    assert store.latest(project_id, item.item_id) == item
    assert store.latest_for_project(project_id) == [item]


@pytest.mark.live
@requires("CLICKHOUSE_HOST", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD")
def test_an_unknown_item_raises_rather_than_returning_an_empty_row() -> None:
    store = _store()
    store.ensure_schema()

    with pytest.raises(RecordNotFound):
        store.latest(scratch_id("live-absent"), scratch_id("absent"))


@pytest.mark.live
@requires("CLICKHOUSE_HOST", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD")
def test_a_project_with_no_script_version_reads_as_none() -> None:
    store = _store()
    store.ensure_schema()

    assert store.latest_script(scratch_id("live-noscript")) is None


@pytest.mark.live
@requires("CLICKHOUSE_HOST", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD")
def test_two_projects_that_minted_the_same_item_id_both_survive_a_merge() -> None:
    """The collision ADR 0014 closes, forced rather than waited for.

    `OPTIMIZE TABLE ... FINAL` runs the background merge on demand. Under
    `ORDER BY item_id` the two rows below were one row, and this merge kept
    the higher version and destroyed the other. Only a real ClickHouse merge
    can show that; a fake never merges anything, so it never had the chance
    to lose a row.
    """
    client = _client()
    store = ClickHouseTrackerStore(client=client)
    store.ensure_schema()
    item_id = scratch_id("EVT")
    ours = _live_item(item_id, scratch_id("live-a"), version=1, state=TrackerState.BLOCKED)
    theirs = _live_item(item_id, scratch_id("live-b"), version=9, state=TrackerState.CLEARED)

    store.save([ours, theirs])
    client.command("OPTIMIZE TABLE tracker_items FINAL")

    assert store.latest(ours.project_id, item_id) == ours
    assert store.latest(theirs.project_id, item_id) == theirs


@pytest.mark.live
@requires("CLICKHOUSE_HOST", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD")
def test_two_versions_of_one_project_both_survive_a_merge() -> None:
    """`script_versions` under `ORDER BY project_id` kept one row per
    project, so v1 was gone the moment v2 landed and the delta path had
    nothing to diff against. Forcing the merge is what proves both rows are
    still there."""
    client = _client()
    store = ClickHouseTrackerStore(client=client)
    store.ensure_schema()
    project_id = scratch_id("live-scripts")
    first = _live_script(project_id, scratch_id("scr"), version=1)
    second = _live_script(project_id, scratch_id("scr"), version=2)

    store.record_script(first)
    store.record_script(second)
    client.command("OPTIMIZE TABLE script_versions FINAL")

    rows = client.query(
        "SELECT version FROM script_versions WHERE project_id = {project_id:String}",
        {"project_id": project_id},
    ).result_rows
    assert sorted(int(row[0]) for row in rows) == [1, 2]
    assert store.latest_script(project_id) == second
