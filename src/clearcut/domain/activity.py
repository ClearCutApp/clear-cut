"""Minimized immutable analytics events; no screenplay or contact contents."""

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class ActivityEvent:
    event_id: str
    organization_id: str
    project_id: str
    kind: str
    occurred_at: str
    source_version: int
    payload: dict[str, Any]
    payload_hash: str
    schema_version: int = 1


_FIELDS = {
    "project_created": {"jurisdiction_code"},
    "revision_saved": {"revision_id"},
    "document_created": {"file_id", "document_kind", "size_bytes"},
    "clearance_changed": {"item_id", "state", "needs_review"},
    "analysis_published": {"analysis_id", "revision_id", "generation_id", "item_count", "counts"},
    "report_created": {"report_id", "analysis_id", "revision_id", "counts", "formula_version"},
}
_COUNTS = {
    "total_retained",
    "confirmed_cleared",
    "needs_review",
    "blocked",
    "in_progress",
    "present",
    "not_detected",
    "unknown_binding",
    "confirmed_cleared_percent",
}


def payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def activity_envelope(
    event_id: str,
    organization_id: str,
    project_id: str,
    kind: str,
    occurred_at: str | datetime,
    source_version: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Freeze dimensions in the same transaction as the source mutation."""
    from dataclasses import asdict

    at = occurred_at.isoformat() if isinstance(occurred_at, datetime) else occurred_at
    event = ActivityEvent(
        event_id,
        organization_id,
        project_id,
        kind,
        at,
        source_version,
        payload,
        payload_hash(payload),
    )
    validate_event(event)
    return {
        **asdict(event),
        "state": "pending",
        "attempt": 0,
        "available_at": datetime(1970, 1, 1, tzinfo=UTC),
    }


def validate_event(event: ActivityEvent) -> None:
    if event.kind not in _FIELDS or set(event.payload) - _FIELDS[event.kind]:
        raise ValueError("unsupported analytics event fields")
    if (
        event.schema_version != 1
        or event.source_version < 0
        or any(
            not value or len(value) > 256
            for value in (event.event_id, event.organization_id, event.project_id)
        )
        or event.payload_hash != payload_hash(event.payload)
    ):
        raise ValueError("invalid analytics event envelope")
    for key, value in event.payload.items():
        if key == "counts":
            if not isinstance(value, dict) or set(value) - _COUNTS:
                raise ValueError("unsupported analytics counts")
            if any(
                type(number) not in {int, float} or not math.isfinite(number) or number < 0
                for number in value.values()
            ):
                raise ValueError("invalid analytics count")
        elif type(value) not in {str, int, bool} or (isinstance(value, str) and len(value) > 256):
            raise ValueError("invalid analytics dimension")


def read_event(value: dict[str, Any]) -> ActivityEvent:
    at = value["occurred_at"]
    event = ActivityEvent(
        str(value["event_id"]),
        str(value["organization_id"]),
        str(value["project_id"]),
        str(value["kind"]),
        at.isoformat() if isinstance(at, datetime) else str(at),
        int(value["source_version"]),
        value["payload"],
        str(value["payload_hash"]),
        int(value.get("schema_version", 0)),
    )
    validate_event(event)
    if datetime.fromisoformat(event.occurred_at.replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("analytics timestamp requires a timezone")
    return event
