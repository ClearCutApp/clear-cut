"""Literal private search uses a request body so query text stays out of URLs."""

from typing import Any

from flask import Blueprint, Response
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import errors, schemas, validators
from clearcut.application.search_project import SearchProject

TAG = "Search"
TAG_DESCRIPTION = "Literal search within an authorized private project."
SCHEMAS: dict[str, Any] = {
    "ProjectSearch": {
        "type": "object",
        "required": ["query"],
        "additionalProperties": False,
        "properties": {
            "query": {"type": "string", "minLength": 2, "maxLength": 200},
            "cursor": {"type": "string", "maxLength": 512},
        },
    },
}
PATHS: dict[str, Any] = {
    "/api/projects/{project_id}/search": {
        "parameters": [schemas.PROJECT_ID],
        "post": {
            "tags": [TAG],
            "operationId": "searchProject",
            "summary": "Search saved script, clearances, document names and recent local research",
            "requestBody": schemas.body(schemas.ref("ProjectSearch")),
            "responses": {
                "200": schemas.ok(
                    "At most 50 literal matches and a continuation cursor.",
                    schemas.json_of({"type": "object"}),
                ),
                "400": schemas.failure("Invalid query or cursor."),
                "404": schemas.NOT_FOUND,
                "409": schemas.failure("Results changed; restart search."),
                "502": schemas.failure("A search source is unavailable."),
            },
        },
    },
}


def create_search_blueprint(search: SearchProject) -> Blueprint:
    bp = Blueprint("clearcut_search", __name__)

    @bp.after_request
    def private_response(response: Response) -> Response:
        response.headers["Cache-Control"] = "no-store"
        return response

    @bp.post("/api/projects/<project_id>/search")
    def search_project(project_id: str) -> ResponseReturnValue:
        payload = validators.json_body()
        query, cursor = payload.get("query"), payload.get("cursor")
        if not isinstance(query, str) or (
            cursor is not None and (not isinstance(cursor, str) or len(cursor) > 512)
        ):
            return errors.error_response(400, "a bounded query and optional cursor are required")
        return errors.run_use_case(lambda: search.execute(project_id, query, cursor))

    return bp
