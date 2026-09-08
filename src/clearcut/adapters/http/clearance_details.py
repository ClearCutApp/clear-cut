"""Versioned clearance evidence and editable permission details."""

from collections.abc import Callable
from typing import Any

from flask import Blueprint, Response, g, request
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import errors, schemas, serializers, validators
from clearcut.application.document_ports import ProjectDocuments
from clearcut.application.get_tracker_item import GetTrackerItem
from clearcut.application.reconfirm_clearance import ReconfirmClearance
from clearcut.application.resolve_finding import EditDetails, ResolveFinding
from clearcut.domain.tracker import ClearanceDetails, InvalidClearance, TrackerConflict, TrackerItem

TAG = "Clearance details"
TAG_DESCRIPTION = "Human-reviewed evidence, conditions, deadlines and permission drafts."
_FIELDS = {
    "note": {"type": "string", "maxLength": 4000},
    "clearance_conditions": {"type": "string", "maxLength": 4000},
    "due_date": {"type": "string", "description": "YYYY-MM-DD or empty to remove the deadline."},
    "assignee_id": {"type": "string", "maxLength": 128},
    "evidence_file_ids": {
        "type": "array",
        "maxItems": 20,
        "uniqueItems": True,
        "items": {"type": "string", "minLength": 1, "maxLength": 128},
    },
    "draft_email": {"type": ["string", "null"], "maxLength": 20000},
}
SCHEMAS: dict[str, Any] = {
    "ClearanceDetailsUpdate": {
        "type": "object",
        "required": ["expected_version", *_FIELDS],
        "properties": {"expected_version": {"type": "integer", "minimum": 1}, **_FIELDS},
        "additionalProperties": False,
    },
}
PATHS: dict[str, Any] = {
    "/api/projects/{project_id}/tracker-items/{item_id}/details": {
        "parameters": [schemas.PROJECT_ID, schemas.ITEM_ID],
        "put": {
            "tags": [TAG],
            "operationId": "updateClearanceDetails",
            "summary": "Save evidence and permission details without changing clearance status",
            "requestBody": schemas.body(schemas.ref("ClearanceDetailsUpdate")),
            "responses": {
                "200": schemas.ok(
                    "New immutable item version.", schemas.json_of(schemas.ref("TrackerItem"))
                ),
                "400": schemas.failure("Invalid details."),
                "403": schemas.failure("Assignment or membership does not allow this action."),
                "404": schemas.NOT_FOUND,
                "409": schemas.failure(
                    "Clearance changed; preserve your local details and reload."
                ),
            },
        },
    },
}


PATHS["/api/projects/{project_id}/tracker-items/{item_id}/permission-request"] = {
    "parameters": [schemas.PROJECT_ID, schemas.ITEM_ID],
    "get": {
        "tags": [TAG],
        "operationId": "downloadPermissionRequest",
        "summary": "Download the reviewed permission draft at the expected item version",
        "parameters": [
            {
                "name": "version",
                "in": "query",
                "required": True,
                "schema": {"type": "integer", "minimum": 1},
            },
            {
                "name": "format",
                "in": "query",
                "schema": {"type": "string", "enum": ["pdf", "txt"], "default": "pdf"},
            },
        ],
        "responses": {
            "200": {
                "description": "Private attachment; never sent to a mailbox.",
                "content": {
                    "application/pdf": {"schema": {"type": "string", "format": "binary"}},
                    "text/plain": {"schema": {"type": "string"}},
                },
            },
            "400": schemas.failure("Save a draft and provide valid parameters."),
            "404": schemas.NOT_FOUND,
            "409": schemas.failure("Clearance changed; reload before exporting."),
        },
    },
}

PATHS["/api/projects/{project_id}/tracker-items/{item_id}/reconfirmation"] = {
    "parameters": [schemas.PROJECT_ID, schemas.ITEM_ID],
    "post": {
        "tags": [TAG],
        "operationId": "reconfirmClearance",
        "summary": "Explicitly confirm evidence and conditions apply to the current revision",
        "requestBody": schemas.body(
            {
                "type": "object",
                "required": ["expected_version", "revision_id", "acknowledged"],
                "properties": {
                    "expected_version": {"type": "integer", "minimum": 1},
                    "revision_id": {"type": "string", "minLength": 1},
                    "acknowledged": {"type": "boolean", "const": True},
                },
            }
        ),
        "responses": {
            "200": schemas.ok(
                "Audited human confirmation.", schemas.json_of(schemas.ref("TrackerItem"))
            ),
            "400": schemas.failure("Explicit acknowledgement and current binding required."),
            "404": schemas.NOT_FOUND,
            "409": schemas.failure("Clearance or analyzed revision changed."),
        },
    },
}


def create_clearance_details_blueprint(
    resolve: ResolveFinding,
    documents: ProjectDocuments,
    get_item: GetTrackerItem,
    permission_document: Callable[[TrackerItem, str], bytes],
    reconfirm: ReconfirmClearance | None = None,
) -> Blueprint:
    bp = Blueprint("clearcut_clearance_details", __name__)

    @bp.post("/api/projects/<project_id>/tracker-items/<item_id>/reconfirmation")
    def confirmation(project_id: str, item_id: str) -> ResponseReturnValue:
        if reconfirm is None:
            return errors.error_response(409, "confirmation requires a committed revision analysis")

        def build() -> dict[str, Any]:
            body = validators.json_body()
            expected, revision = body.get("expected_version"), body.get("revision_id")
            if (
                type(expected) is not int
                or expected < 1
                or not isinstance(revision, str)
                or not revision
                or body.get("acknowledged") is not True
            ):
                raise InvalidClearance("acknowledge the current revision, evidence and conditions")
            return serializers.tracker_item_json(
                reconfirm.execute(
                    project_id, item_id, expected, revision, g.identity.user_id, validators.now()
                )
            )

        return errors.run_use_case(build)

    @bp.put("/api/projects/<project_id>/tracker-items/<item_id>/details")
    def update(project_id: str, item_id: str) -> ResponseReturnValue:
        def build() -> dict[str, Any]:
            body = validators.json_body()
            expected = body.get("expected_version")
            if type(expected) is not int or expected < 1:
                raise InvalidClearance("expected_version must be a positive integer")
            if set(body) != {"expected_version", *_FIELDS}:
                raise InvalidClearance("supply every clearance detail field")
            evidence = body["evidence_file_ids"]
            if not isinstance(evidence, list) or any(
                not isinstance(value, str) for value in evidence
            ):
                raise InvalidClearance("evidence_file_ids must be a list of file identifiers")
            details = ClearanceDetails(
                body["note"],
                body["clearance_conditions"],
                body["due_date"],
                body["assignee_id"],
                tuple(evidence),
                body["draft_email"],
            )
            for file_id in details.evidence_file_ids:
                documents.metadata(project_id, file_id)
            identity = getattr(g, "identity", None)
            item = resolve.execute(
                project_id,
                item_id,
                EditDetails(details),
                validators.now(),
                expected_version=expected,
                actor=identity.user_id if identity else "demo",
            )
            return serializers.tracker_item_json(item)

        return errors.run_use_case(build)

    @bp.get("/api/projects/<project_id>/tracker-items/<item_id>/permission-request")
    def download(project_id: str, item_id: str) -> ResponseReturnValue:
        def build() -> Response:
            version = request.args.get("version", "")
            format_name = request.args.get("format", "pdf")
            if not version.isdecimal() or int(version) < 1 or format_name not in {"pdf", "txt"}:
                raise InvalidClearance("choose a positive version and PDF or TXT format")
            item = get_item.execute(project_id, item_id)
            if item.version != int(version):
                raise TrackerConflict(item.version)
            if not item.draft_email or not item.draft_email.strip():
                raise InvalidClearance("save a permission-request draft before downloading")
            content = permission_document(item, format_name)
            return Response(
                content,
                mimetype="application/pdf" if format_name == "pdf" else "text/plain",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="permission-request-v{item.version}.{format_name}"'
                    ),
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                },
            )

        return errors.run_use_case(build)

    return bp
