"""Authorized, explicit Parallel research for saved production locations."""

import uuid
from datetime import UTC, datetime
from typing import Any

from flask import Blueprint, Response, g
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import errors, schemas, validators
from clearcut.application.local_research_ports import LocalResearchStore
from clearcut.application.research_production_location import ResearchProductionLocation
from clearcut.domain.workspace import InvalidWorkspace

TAG = "Local research"
TAG_DESCRIPTION = "Dated official evidence for private project production locations."
SCHEMAS: dict[str, Any] = {
    "LocalResearchCreate": {
        "type": "object",
        "required": ["expected_settings_version", "location_index", "question"],
        "properties": {
            "expected_settings_version": {"type": "integer", "minimum": 1},
            "location_index": {"type": "integer", "minimum": 0},
            "question": {"type": "string", "minLength": 1, "maxLength": 2000},
        },
        "additionalProperties": False,
    },
}
PATHS: dict[str, Any] = {
    "/api/projects/{project_id}/local-research": {
        "parameters": [schemas.PROJECT_ID],
        "get": {
            "tags": [TAG],
            "operationId": "listLocalResearch",
            "summary": "Read the latest 50 saved location research records",
            "responses": {
                "200": schemas.ok("Dated research records.", schemas.json_of({"type": "object"})),
                "404": schemas.NOT_FOUND,
            },
        },
        "post": {
            "tags": [TAG],
            "operationId": "researchProductionLocation",
            "summary": "Research a saved location with Parallel and retain cited official evidence",
            "requestBody": schemas.body(schemas.ref("LocalResearchCreate")),
            "responses": {
                "200": schemas.ok(
                    "Saved evidence or explicit coverage gap.", schemas.json_of({"type": "object"})
                ),
                "400": schemas.failure("Invalid location or question."),
                "404": schemas.NOT_FOUND,
                "409": schemas.failure("Production settings changed."),
                "502": schemas.failure("Research provider unavailable."),
            },
        },
    },
}


def create_local_research_blueprint(
    store: LocalResearchStore | None, research: ResearchProductionLocation | None
) -> Blueprint:
    bp = Blueprint("clearcut_local_research", __name__)

    @bp.after_request
    def private_response(response: Response) -> Response:
        response.headers["Cache-Control"] = "no-store"
        return response

    def serialized(record: dict[str, Any]) -> dict[str, Any]:
        return {**record, "created_at": record["created_at"].isoformat()}

    @bp.get("/api/projects/<project_id>/local-research")
    def list_research(project_id: str) -> ResponseReturnValue:
        if store is None:
            return {"configured": False, "research": []}
        return errors.run_use_case(
            lambda: {
                "configured": True,
                "research": [serialized(record) for record in store.list(project_id)],
            }
        )

    @bp.post("/api/projects/<project_id>/local-research")
    def create_research(project_id: str) -> ResponseReturnValue:
        if research is None:
            return {"error": "Local research requires a configured account."}, 503
        payload = validators.json_body()

        def execute() -> dict[str, Any]:
            version, index, question = (
                payload.get("expected_settings_version"),
                payload.get("location_index"),
                payload.get("question"),
            )
            if (
                type(version) is not int
                or version < 1
                or type(index) is not int
                or index < 0
                or not isinstance(question, str)
                or not 1 <= len(question.strip()) <= 2000
            ):
                raise InvalidWorkspace("select saved settings, a location and a bounded question")
            return serialized(
                research.execute(
                    project_id,
                    g.identity.user_id,
                    uuid.uuid4().hex,
                    version,
                    index,
                    question,
                    datetime.now(UTC),
                )
            )

        return errors.run_use_case(execute)

    return bp
