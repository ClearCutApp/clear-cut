"""Append-only analytics history with query-time event deduplication."""

from __future__ import annotations

import builtins
import json
from datetime import UTC, datetime
from typing import Any

from clearcut.adapters.clickhouse import client as ch_client
from clearcut.domain.activity import ActivityEvent, read_event, validate_event

DDL = """
CREATE TABLE IF NOT EXISTS analytics_events (
    organization_id String,
    project_id String,
    event_id String,
    kind LowCardinality(String),
    occurred_at DateTime64(6, 'UTC'),
    source_version UInt64,
    schema_version UInt16,
    payload String,
    payload_hash String
) ENGINE = MergeTree
ORDER BY (organization_id, project_id, event_id)
"""
_COLUMNS = [
    "organization_id",
    "project_id",
    "event_id",
    "kind",
    "occurred_at",
    "source_version",
    "schema_version",
    "payload",
    "payload_hash",
]


class ClickHouseActivity:
    def __init__(self, client: ch_client._ChClient) -> None:
        self.client = client

    def ensure_schema(self) -> None:
        try:
            self.client.command(DDL)
        except Exception as exc:
            raise ch_client.ClickHouseUnavailable("analytics schema unavailable") from exc

    def append(self, event: ActivityEvent) -> None:
        validate_event(event)
        at = datetime.fromisoformat(event.occurred_at.replace("Z", "+00:00"))
        if at.tzinfo is None:
            raise ValueError("analytics timestamps require a timezone")
        row = [
            event.organization_id,
            event.project_id,
            event.event_id,
            event.kind,
            at.astimezone(UTC),
            event.source_version,
            event.schema_version,
            json.dumps(event.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            event.payload_hash,
        ]
        try:
            self.client.insert("analytics_events", [row], column_names=_COLUMNS)
        except Exception as exc:
            raise ch_client.ClickHouseUnavailable("analytics insertion unavailable") from exc

    def _read(
        self, organization_id: str, project_id: str, before: tuple[str, str] | None, trends: bool
    ) -> list[ActivityEvent]:
        # Grouping precedes pagination/aggregation: background merges are not
        # required for a lost-ack redelivery to count as one logical event.
        predicate = " AND kind = 'analysis_published'" if trends else ""
        parameters: dict[str, Any] = {"organization": organization_id, "project": project_id}
        if before:
            predicate += (
                " AND (occurred_at, event_id) < ({at:DateTime64(6, 'UTC')}, {event:String})"
            )
            parameters.update(
                at=datetime.fromisoformat(before[0].replace("Z", "+00:00")), event=before[1]
            )
        query = (
            """
SELECT organization_id, project_id, event_id, kind, occurred_at,
       source_version, schema_version, payload, payload_hash, variants
FROM (
    SELECT organization_id, project_id, event_id, any(e.kind) AS kind,
           any(e.occurred_at) AS occurred_at, any(e.source_version) AS source_version,
           any(e.schema_version) AS schema_version, any(e.payload) AS payload,
           any(e.payload_hash) AS payload_hash,
           uniqExact(tuple(e.kind, e.occurred_at, e.source_version, e.schema_version,
                           e.payload, e.payload_hash)) AS variants
    FROM analytics_events AS e
    WHERE organization_id = {organization:String} AND project_id = {project:String}
    GROUP BY organization_id, project_id, event_id
)
WHERE 1
"""
            + predicate
            + " ORDER BY occurred_at DESC, event_id DESC LIMIT 50"
        )
        try:
            result = self.client.query(query, parameters=parameters)
            events = []
            for row in result.result_rows:
                if row[-1] != 1:
                    raise ValueError("analytics event identity has conflicting payloads")
                value = dict(zip(_COLUMNS, row[:-1], strict=True))
                value["payload"] = json.loads(value["payload"])
                event = read_event(value)
                if event.organization_id != organization_id or event.project_id != project_id:
                    raise ValueError("analytics result scope mismatch")
                events.append(event)
            if len({event.event_id for event in events}) != len(events):
                raise ValueError("analytics event identity has conflicting payloads")
            return events
        except Exception as exc:
            raise ch_client.ClickHouseUnavailable("analytics query unavailable") from exc

    def list(
        self, organization_id: str, project_id: str, before: tuple[str, str] | None = None
    ) -> list[ActivityEvent]:
        return self._read(organization_id, project_id, before, False)

    def trends(self, organization_id: str, project_id: str) -> builtins.list[ActivityEvent]:
        return self._read(organization_id, project_id, None, True)
