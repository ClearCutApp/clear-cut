"""Project-scoped notification history and private per-user read marks."""

from typing import Any

from flask import Blueprint, Response, g, request
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import errors, schemas, validators
from clearcut.application.notification_ports import ProjectNotifications

TAG = "Notifications"
TAG_DESCRIPTION = "Private producer attention records and optional scoped delivery status."
SCHEMAS: dict[str, Any] = {}
PATHS: dict[str, Any] = {
    "/api/projects/{project_id}/notifications": {
        "parameters": [schemas.PROJECT_ID],
        "get": {
            "tags": [TAG],
            "operationId": "listProjectNotifications",
            "summary": "Read 50 notifications, newest first, with private read marks",
            "parameters": [{"name": "before", "in": "query", "schema": {"type": "string"}}],
            "responses": {
                "200": schemas.ok(
                    "Notifications and optional next cursor.", schemas.json_of({"type": "object"})
                ),
                "404": schemas.NOT_FOUND,
            },
        },
    },
    "/api/projects/{project_id}/notifications/{notification_id}/read": {
        "parameters": [
            schemas.PROJECT_ID,
            {
                "name": "notification_id",
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            },
        ],
        "post": {
            "tags": [TAG],
            "operationId": "readProjectNotification",
            "summary": "Mark a notification read for the signed-in user",
            "responses": {
                "200": schemas.ok("Read mark saved.", schemas.json_of({"type": "object"})),
                "404": schemas.NOT_FOUND,
            },
        },
    },
}


def create_notifications_blueprint(store: ProjectNotifications | None) -> Blueprint:
    bp = Blueprint("clearcut_notifications", __name__)

    @bp.after_request
    def private_response(response: Response) -> Response:
        response.headers["Cache-Control"] = "no-store"
        return response

    @bp.get("/api/projects/<project_id>/notifications")
    def list_notifications(project_id: str) -> ResponseReturnValue:
        if store is None:
            return {"configured": False, "notifications": [], "next_cursor": None}
        before = request.args.get("before")
        if before is not None and (
            len(before) != 32 or any(c not in "0123456789abcdef" for c in before)
        ):
            return errors.error_response(400, "invalid notification cursor")

        def execute() -> dict[str, Any]:
            assert store is not None
            values = store.list(project_id, g.identity.user_id, before)
            return {
                "configured": True,
                "notifications": values,
                "next_cursor": values[-1]["notification_id"] if len(values) == 50 else None,
            }

        return errors.run_use_case(execute)

    @bp.post("/api/projects/<project_id>/notifications/<notification_id>/read")
    def read_notification(project_id: str, notification_id: str) -> ResponseReturnValue:
        if store is None:
            return {"error": "Notifications require a configured account."}, 503

        def execute() -> dict[str, Any]:
            assert store is not None
            store.read(project_id, g.identity.user_id, notification_id, validators.now())
            return {"read": True}

        return errors.run_use_case(execute)

    return bp
