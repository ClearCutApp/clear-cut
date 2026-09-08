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

from flask import Blueprint, g, request
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import errors, schemas, serializers, validators
from clearcut.application.create_project import CreateProject
from clearcut.application.get_project import GetProject
from clearcut.application.list_projects import ListProjects
from clearcut.application.workspace_ports import ProjectAccess
from clearcut.domain.jurisdiction import JURISDICTIONS, Jurisdiction
from clearcut.domain.project import Project

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
            "organization_id": {"type": "string", "description": "Required in live mode."},
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

SCHEMAS["Organization"] = {
    "type": "object",
    "required": ["organization_id", "name", "role"],
    "properties": {key: {"type": "string"} for key in ("organization_id", "name", "role")},
}
PATHS: JsonDict = {
    "/api/organizations": {
        "get": {
            "tags": [TAG],
            "operationId": "listOrganizations",
            "summary": "Active memberships of this user",
            "responses": {
                "200": schemas.ok("Workspaces.", schemas.json_array_of(schemas.ref("Organization")))
            },
        },
        "post": {
            "tags": [TAG],
            "operationId": "createOrganization",
            "summary": "Create a private workspace and owner membership",
            "requestBody": schemas.body(
                {
                    "type": "object",
                    "required": ["name"],
                    "properties": {"name": {"type": "string", "minLength": 1}},
                }
            ),
            "responses": {
                "201": schemas.ok("Workspace.", schemas.json_of(schemas.ref("Organization")))
            },
        },
    },
    "/api/jurisdictions": {
        "get": {
            "tags": [TAG],
            "operationId": "listJurisdictions",
            "summary": "The jurisdictions a project can be cleared against",
            "description": (
                "The selectable codes `jurisdiction_code` accepts anywhere in this API. A "
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
    access: ProjectAccess | None = None,
) -> Blueprint:
    bp = Blueprint("clearcut_projects", __name__)

    @bp.route("/api/jurisdictions", methods=["GET"])
    def list_jurisdictions() -> ResponseReturnValue:
        return errors.run_use_case(
            lambda: [serializers.jurisdiction_json(jurisdiction) for jurisdiction in JURISDICTIONS]
        )

    @bp.route("/api/projects", methods=["GET"])
    def projects_index() -> ResponseReturnValue:
        def visible() -> list[JsonDict]:
            if access is None:
                return [serializers.project_json(project) for project in list_projects.execute()]
            return [
                serializers.project_json(access.get_project(project_id))
                for project_id in sorted(access.visible_project_ids(g.identity.user_id))
            ]

        return errors.run_use_case(visible)

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

        organization_id = str(payload.get("organization_id", ""))
        if access is not None and (not organization_id or "/" in organization_id):
            return errors.error_response(400, "organization_id is required")

        def build() -> JsonDict:
            if access is not None:
                project = Project(project_id, title, jurisdiction.code, at)
                access.create_project(g.identity.user_id, organization_id, project)
                return serializers.project_json(project)
            return serializers.project_json(
                create_project.execute(project_id, title, jurisdiction, at)
            )

        return errors.run_use_case(build, status=201, location=f"/api/projects/{project_id}")

    @bp.route("/api/projects/<project_id>", methods=["GET"])
    def projects_show(project_id: str) -> ResponseReturnValue:
        return errors.run_use_case(
            lambda: serializers.project_json(
                access.get_project(project_id)
                if access is not None
                else get_project.execute(project_id)
            )
        )

    @bp.route("/api/organizations", methods=["GET", "POST"])
    def organizations() -> ResponseReturnValue:
        if access is None:
            return errors.error_response(409, "workspaces require live identity")
        if request.method == "GET":
            return errors.run_use_case(lambda: list(access.organizations(g.identity.user_id)))
        payload = validators.json_body()
        name = validators.require_field(payload, "name")
        if not isinstance(name, str):
            return name
        organization_id = validators.new_id()

        def build_organization() -> JsonDict:
            access.create_organization(g.identity.user_id, organization_id, name)
            return {"organization_id": organization_id, "name": name, "role": "owner"}

        return errors.run_use_case(build_organization, status=201)

    return bp
