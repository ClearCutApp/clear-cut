"""`ClickHouseTrackerStore` against ClickHouse Cloud.

The proof is the round trip itself. `scene_numbers` is a Python tuple stored in
an `Array(UInt32)` column and `needs_review` a bool stored in `UInt8`, so an
item that comes back equal to the one that went in is an item ClickHouse
genuinely serialized, stored, and re-read. A fake returning the object it was
handed proves neither column mapping.

`ensure_schema()` runs first because nothing else creates the tables --
`composition.py` never calls it, so a live test that skips it fails on a missing
table rather than on anything meaningful.
"""

from typing import cast

import clickhouse_connect
import pytest

from clearcut.adapters.clickhouse.client import _ChClient
from clearcut.adapters.clickhouse.tracker import ClickHouseTrackerStore
from clearcut.composition import _clickhouse_host
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.tracker import TrackerItem, TrackerState
from tests.live.conftest import env, requires, scratch_id


def _store() -> ClickHouseTrackerStore:
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
    return ClickHouseTrackerStore(client=client)


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

    assert store.latest(item.item_id) == item
    assert store.latest_for_project(project_id) == [item]


@pytest.mark.live
@requires("CLICKHOUSE_HOST", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD")
def test_an_unknown_item_raises_rather_than_returning_an_empty_row() -> None:
    store = _store()
    store.ensure_schema()

    with pytest.raises(RecordNotFound):
        store.latest(scratch_id("absent"))


@pytest.mark.live
@requires("CLICKHOUSE_HOST", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD")
def test_a_project_with_no_script_version_reads_as_none() -> None:
    store = _store()
    store.ensure_schema()

    assert store.latest_script(scratch_id("live-noscript")) is None
