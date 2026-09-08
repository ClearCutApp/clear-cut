"""Project-authorized activity and analysis trends served by ClickHouse."""

import base64
import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

from flask import Blueprint, g, request
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import errors, schemas
from clearcut.application.activity_ports import ActivityStore

TAG = "Activity"
TAG_DESCRIPTION = "Private immutable event history and analysis trends projected into ClickHouse."
SCHEMAS: dict[str, Any] = {
    "ActivityEvent": {
        "type": "object",
        "required": ["event_id", "kind", "occurred_at", "payload"],
        "properties": {
            "event_id": {"type": "string"},
            "kind": {"type": "string"},
            "occurred_at": {"type": "string", "format": "date-time"},
            "source_version": {"type": "integer"},
            "payload": {"type": "object"},
        },
    },
}
PATHS: dict[str, Any] = {
    "/api/projects/{project_id}/activity": {
        "parameters": [schemas.PROJECT_ID],
        "get": {
            "tags": [TAG],
            "operationId": "getProjectActivity",
            "summary": "Read deduplicated project history and committed analysis trends",
            "parameters": [{"name": "before", "in": "query", "schema": {"type": "string"}}],
            "responses": {
                "200": schemas.ok(
                    "Private eventual projection.",
                    schemas.json_of(
                        {
                            "type": "object",
                            "properties": {
                                "configured": {"type": "boolean"},
                                "events": {"type": "array", "items": schemas.ref("ActivityEvent")},
                                "trends": {"type": "array", "items": schemas.ref("ActivityEvent")},
                                "next_before": {"type": ["string", "null"]},
                            },
                        }
                    ),
                ),
                "400": schemas.failure("Invalid page cursor."),
                "404": schemas.NOT_FOUND,
                "502": schemas.failure("Activity projection unavailable."),
            },
        },
    },
}


def create_activity_blueprint(activity: ActivityStore | None) -> Blueprint:
    bp = Blueprint("clearcut_activity", __name__)

    @bp.get("/api/projects/<project_id>/activity")
    def index(project_id: str) -> ResponseReturnValue:
        before = None
        cursor = request.args.get("before")
        if cursor:
            try:
                if len(cursor) > 1024:
                    raise ValueError("cursor too long")
                values = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
                if (
                    not isinstance(values, list)
                    or len(values) != 2
                    or any(not isinstance(value, str) or len(value) > 256 for value in values)
                    or datetime.fromisoformat(values[0]).tzinfo is None
                ):
                    raise ValueError("invalid cursor")
                before = (values[0], values[1])
            except (ValueError, TypeError):
                return errors.error_response(400, "invalid activity cursor")

        def build() -> dict[str, Any]:
            if activity is None:
                return {"configured": False, "events": [], "trends": [], "next_before": None}
            events = activity.list(g.organization_id, project_id, before)
            trends = activity.trends(g.organization_id, project_id) if before is None else []
            next_before = (
                base64.urlsafe_b64encode(
                    json.dumps([events[-1].occurred_at, events[-1].event_id]).encode()
                )
                .decode()
                .rstrip("=")
                if len(events) == 50
                else None
            )
            return {
                "configured": True,
                "events": [asdict(event) for event in events],
                "trends": [asdict(event) for event in trends],
                "next_before": next_before,
            }

        return errors.run_use_case(build)

    return bp
