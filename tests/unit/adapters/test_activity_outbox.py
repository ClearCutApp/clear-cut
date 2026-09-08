"""Accepted inserts, lease fencing, bounded retries and minimized source events."""

from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from clearcut.adapters.clickhouse.activity import ClickHouseActivity
from clearcut.adapters.clickhouse.client import ClickHouseUnavailable
from clearcut.adapters.gcp.activity_outbox import FirestoreActivityOutbox
from clearcut.domain.activity import activity_envelope, read_event
from clearcut.domain.durable_analysis import LeaseLost
from tests.unit.adapters.test_clearance_transactions import AtomicClient
from tests.unit.adapters.test_durable_jobs import NOW


def queued() -> tuple[AtomicClient, FirestoreActivityOutbox]:
    client = AtomicClient()
    client.data["outbox/event"] = activity_envelope(
        "event",
        "org",
        "project",
        "clearance_changed",
        NOW,
        2,
        {"item_id": "item", "state": "CLEARED", "needs_review": False},
    )
    return client, FirestoreActivityOutbox(client)


def test_accepted_insert_lost_ack_replays_identical_event_and_stale_owner_cannot_ack():
    client, outbox = queued()
    first = outbox.claim("event", "first", NOW)
    assert first is not None
    assert outbox.claim("event", "second", NOW) is None
    rows: list[list[Any]] = []
    clickhouse = ClickHouseActivity(
        SimpleNamespace(insert=lambda table, data, column_names: rows.extend(data))
    )
    clickhouse.append(first.event)
    later = NOW + timedelta(seconds=91)
    second = outbox.claim("event", "second", later)
    assert second is not None and second.fence > first.fence
    with pytest.raises(LeaseLost):
        outbox.acknowledge(first, later)
    clickhouse.append(second.event)
    assert rows[0] == rows[1]
    outbox.acknowledge(second, later)
    assert client.data["outbox/event"]["state"] == "delivered"
    assert outbox.claim("event", "third", later) is None


def test_failure_backoff_is_bounded_and_invalid_legacy_envelope_is_quarantined():
    client, outbox = queued()
    at = NOW
    for attempt in range(1, 6):
        lease = outbox.claim("event", "worker", at)
        assert lease is not None and lease.attempt == attempt
        outbox.fail(lease, at)
        assert outbox.claim("event", "worker", at) is None
        at += timedelta(seconds=301)
    assert client.data["outbox/event"]["state"] == "failed"
    client.data["outbox/legacy"] = {
        "kind": "project_created",
        "state": "pending",
        "payload": {"title": "private title"},
    }
    assert outbox.claim("legacy", "worker", at) is None
    assert client.data["outbox/legacy"]["state"] == "quarantined"


def test_projection_query_deduplicates_before_page_limit_and_rejects_conflicting_identity():
    client, _ = queued()
    event = read_event(client.data["outbox/event"])
    calls = []
    import json

    row = (
        "org",
        "project",
        "event",
        event.kind,
        NOW,
        2,
        1,
        json.dumps(event.payload),
        event.payload_hash,
        1,
    )

    def query(sql, parameters):
        calls.append((sql, parameters))
        return SimpleNamespace(result_rows=[row])

    activity = ClickHouseActivity(SimpleNamespace(query=query))
    assert activity.list("org", "project") == [event]
    sql, parameters = calls[0]
    assert sql.index("GROUP BY") < sql.index("LIMIT 50")
    assert "uniqExact" in sql
    assert parameters == {"organization": "org", "project": "project"}
    row = (*row[:-1], 2)
    with pytest.raises(ClickHouseUnavailable):
        activity.list("org", "project")


def test_event_contract_rejects_content_and_tampered_payload_hash():
    with pytest.raises(ValueError):
        activity_envelope(
            "event",
            "org",
            "project",
            "clearance_changed",
            NOW,
            1,
            {"item_id": "item", "note": "private screenplay"},
        )
    client, _ = queued()
    client.data["outbox/event"]["payload"]["state"] = "BLOCKED"
    with pytest.raises(ValueError):
        read_event(client.data["outbox/event"])
