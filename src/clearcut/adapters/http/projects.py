"""Projects, and the jurisdictions they can be cleared against.

The endpoint ADR 0011 cut and ADR 0012 reinstated. Without a create route a
producer cannot make the thing every other path hangs off, and `project_id`
stays an arbitrary string two people can collide on by typing the same word.
The server mints the id here for exactly that reason.

`GET /api/jurisdictions` reads a domain constant and touches no port. That is
not an omission: reading `domain.jurisdiction.JURISDICTIONS` is not I/O, so a
port for it would be a port with one in-process implementation, which
AGENT.md section 4 bans.
"""

from typing import Any

from flask import Blueprint
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import errors, schemas, serializers, validators
from clearcut.application.create_project import CreateProject
from clearcut.application.get_project import GetProject
from clearcut.application.list_projects import ListProjects
from clearcut.domain.jurisdiction import JURISDICTIONS, Jurisdiction

JsonDict = dict[str, Any]

TAG = "Projects"

TAG_DESCRIPTION = "Projects and the jurisdictions they can be cleared against."

SCHEMAS: JsonDict = {
    "Jurisdiction": {
        "type": "object",
        "required": ["code", "display_name"],
        "properties": {
            "code": {
                "type": "string",
                "description": (
                    "The ISO 3166-1 alpha-2 code every `jurisdiction_code` field takes."
                ),
            },
            "display_name": {"type": "string"},
        },
        "additionalProperties": False,
    },
    "ProjectCreate": {
        "type": "object",
        "required": ["title", "jurisdiction_code"],
        "properties": {
            "title": {"type": "string", "minLength": 1},
            "jurisdiction_code": {
                "type": "string",
                "description": "One of the codes `GET /api/jurisdictions` returns.",
            },
        },
        "additionalProperties": False,
    },
    "Project": {
        "type": "object",
        "required": ["project_id", "title", "jurisdiction_code", "created_at"],
        "properties": {
            "project_id": {"type": "string"},
            "title": {"type": "string"},
            "jurisdiction_code": {"type": "string"},
            "created_at": {
                "type": "string",
                "format": "date-time",
                "description": "UTC, seconds precision.",
            },
        },
        "additionalProperties": False,
    },
}

PATHS: JsonDict = {
    "/api/jurisdictions": {
        "get": {
            "tags": [TAG],
            "operationId": "listJurisdictions",
            "summary": "The jurisdictions a project can be cleared against",
            "description": (
                "The ten codes `jurisdiction_code` accepts anywhere in this API. A "
                "jurisdiction's legal corpus prefix is deliberately absent: it names "
                "a bucket layout, which is the server's business."
            ),
            "responses": {
                "200": schemas.ok(
                    "Every supported jurisdiction, in display order.",
                    schemas.json_array_of(schemas.ref("Jurisdiction")),
                ),
                "500": schemas.INTERNAL_ERROR,
            },
        }
    },
    "/api/projects": {
        "get": {
            "tags": [TAG],
            "operationId": "listProjects",
            "summary": "Every project",
            "responses": {
                "200": schemas.ok(
                    "The projects this instance holds. An empty array when there are none.",
                    schemas.json_array_of(schemas.ref("Project")),
                ),
                "500": schemas.INTERNAL_ERROR,
            },
        },
        "post": {
            "tags": [TAG],
            "operationId": "createProject",
            "summary": "Create a project",
            "requestBody": schemas.body(schemas.ref("ProjectCreate")),
            "responses": {
                "201": schemas.created(
                    "The project as stored. `Location` carries its canonical path.",
                    schemas.json_of(schemas.ref("Project")),
                    location="The path of the created project.",
                ),
                "400": schemas.BAD_REQUEST,
                "500": schemas.INTERNAL_ERROR,
            },
        },
    },
    "/api/projects/{project_id}": {
        "parameters": [schemas.PROJECT_ID],
        "get": {
            "tags": [TAG],
            "operationId": "getProject",
            "summary": "One project",
            "responses": {
                "200": schemas.ok("The project.", schemas.json_of(schemas.ref("Project"))),
                "404": schemas.NOT_FOUND,
                "500": schemas.INTERNAL_ERROR,
            },
        },
    },
}


def create_projects_blueprint(
    create_project: CreateProject,
    list_projects: ListProjects,
    get_project: GetProject,
) -> Blueprint:
    bp = Blueprint("clearcut_projects", __name__)

    @bp.route("/api/jurisdictions", methods=["GET"])
    def list_jurisdictions() -> ResponseReturnValue:
        return errors.run_use_case(
            lambda: [serializers.jurisdiction_json(jurisdiction) for jurisdiction in JURISDICTIONS]
        )

    @bp.route("/api/projects", methods=["GET"])
    def projects_index() -> ResponseReturnValue:
        return errors.run_use_case(
            lambda: [serializers.project_json(project) for project in list_projects.execute()]
        )

    @bp.route("/api/projects", methods=["POST"])
    def projects_create() -> ResponseReturnValue:
        payload = validators.json_body()
        title = validators.require_field(payload, "title")
        if not isinstance(title, str):
            return title
        jurisdiction = validators.resolve_jurisdiction(str(payload.get("jurisdiction_code", "")))
        if not isinstance(jurisdiction, Jurisdiction):
            return jurisdiction
        project_id = validators.new_id()
        at = validators.now()

        def build() -> JsonDict:
            return serializers.project_json(
                create_project.execute(project_id, title, jurisdiction, at)
            )

        return errors.run_use_case(build, status=201, location=f"/api/projects/{project_id}")

    @bp.route("/api/projects/<project_id>", methods=["GET"])
    def projects_show(project_id: str) -> ResponseReturnValue:
        return errors.run_use_case(
            lambda: serializers.project_json(get_project.execute(project_id))
        )

    return bp
