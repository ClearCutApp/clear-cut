"""Projects, and the jurisdictions they can be cleared against.

The endpoint ADR 0011 cut and ADR 0012 reinstated. Without a create route a
producer cannot make the thing every other path hangs off, and `project_id`
stays an arbitrary string two people can collide on by typing the same word.
The server mints the id here for exactly that reason.

`GET /api/jurisdictions` reads a domain constant and touches no port. That is
not an omission: reading `domain.jurisdiction.JURISDICTIONS` is not I/O, so a
port for it would be a port with one in-process implementation, which
AGENT.md section 4 bans.

`PUT`/`DELETE /api/projects/{project_id}/favourite` reaches a different port
from every other route here. A favourite is one user's mark on a project, not
a property of it, so it is neither on the `Project` aggregate nor in the
project store: `ProjectFavourites` owns it, and this module only joins the
caller's marks to the projects it was already going to serve.
"""

from typing import Any

from flask import Blueprint, g, request
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import errors, schemas, serializers, validators
from clearcut.application.create_project import CreateProject
from clearcut.application.get_project import GetProject
from clearcut.application.list_projects import ListProjects
from clearcut.application.ports import ClearanceSummaries
from clearcut.application.workspace_ports import ProjectAccess, ProjectFavourites
from clearcut.domain.jurisdiction import JURISDICTIONS, Jurisdiction
from clearcut.domain.project import PROJECT_FORMATS, PROJECT_STATUSES, Project
from clearcut.domain.tracker import EMPTY_CLEARANCE_SUMMARY, ClearanceSummary

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
    "ProjectFormat": {
        "type": ["string", "null"],
        "enum": [*sorted(PROJECT_FORMATS), None],
        "description": (
            "What kind of production this is. `null` means nobody has said; a client "
            "shows nothing rather than guessing one."
        ),
    },
    "ProjectStatus": {
        "type": ["string", "null"],
        "enum": [*sorted(PROJECT_STATUSES), None],
        "description": "Where the production has reached. `null` means nobody has said.",
    },
    "ProjectPosterUri": {
        "type": ["string", "null"],
        "description": (
            "Where this project's poster art lives. `null` when none has been set, "
            "which is the default: the server never invents one, and a client draws "
            "whatever placeholder it likes rather than a poster this project does not "
            "have. Nothing in this API uploads or fetches the image."
        ),
    },
    "ClearanceSummary": {
        "type": "object",
        "required": ["total", "cleared", "in_progress", "blocked", "needs_review"],
        "properties": {
            "total": {
                "type": "integer",
                "minimum": 0,
                "description": "Every clearance item this project holds; the denominator.",
            },
            "cleared": {"type": "integer", "minimum": 0},
            "in_progress": {"type": "integer", "minimum": 0},
            "blocked": {"type": "integer", "minimum": 0},
            "needs_review": {
                "type": "integer",
                "minimum": 0,
                "description": (
                    "Items flagged for a producer to look at again. An item counts "
                    "here instead of in its state, never in both, so the four "
                    "buckets sum to `total`."
                ),
            },
        },
        "additionalProperties": False,
        "description": (
            "The clearance totals of one project, counted the way the tracker page "
            "counts them. No percentage: the bar is `cleared / total`, and a second "
            "server-side definition of how cleared a project is would be one a "
            "reader has to reconcile. All zero means nobody has analysed this "
            "project yet -- never that the numbers are unknown."
        ),
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
            "poster_uri": schemas.ref("ProjectPosterUri"),
            "format": schemas.ref("ProjectFormat"),
            "status": schemas.ref("ProjectStatus"),
        },
        "additionalProperties": False,
    },
    "Project": {
        "type": "object",
        "required": [
            "project_id",
            "title",
            "jurisdiction_code",
            "created_at",
            "poster_uri",
            "format",
            "status",
            "favourite",
        ],
        "properties": {
            "project_id": {"type": "string"},
            "title": {"type": "string"},
            "jurisdiction_code": {"type": "string"},
            "created_at": {
                "type": "string",
                "format": "date-time",
                "description": "UTC, seconds precision.",
            },
            "poster_uri": schemas.ref("ProjectPosterUri"),
            "format": schemas.ref("ProjectFormat"),
            "status": schemas.ref("ProjectStatus"),
            "favourite": {
                "type": "boolean",
                "description": (
                    "Whether the caller has marked this project. Per user, never per "
                    "project: two producers reading the same project see two answers."
                ),
            },
            "clearance": schemas.ref("ClearanceSummary"),
        },
        "additionalProperties": False,
    },
    "ProjectFavourite": {
        "type": "object",
        "required": ["project_id", "favourite"],
        "properties": {
            "project_id": {"type": "string"},
            "favourite": {"type": "boolean"},
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
            "description": (
                "Each project carries a `clearance` object -- the totals its row "
                "draws a progress bar from -- so a client never asks for one "
                "tracker per row to render one list. A project nobody has analysed "
                "reports zeroes. The key is absent altogether only where the "
                "instance serves no clearance totals, which is not the same claim "
                "as zero; a client that ignores it reads exactly the list it "
                "always did."
            ),
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
    "/api/projects/{project_id}/favourite": {
        "parameters": [schemas.PROJECT_ID],
        "put": {
            "tags": [TAG],
            "operationId": "addProjectFavourite",
            "summary": "Mark this project as one of the caller's favourites",
            "description": (
                "Idempotent: marking an already-marked project is the same request "
                "again, not an error. A project the caller cannot read answers 404, "
                "the same as reading it would -- the marker never confirms that a "
                "project exists somewhere the caller has no access to."
            ),
            "responses": {
                "200": schemas.ok(
                    "The project is marked.", schemas.json_of(schemas.ref("ProjectFavourite"))
                ),
                "404": schemas.NOT_FOUND,
                "409": schemas.failure("This instance serves no favourites store."),
                "500": schemas.INTERNAL_ERROR,
            },
        },
        "delete": {
            "tags": [TAG],
            "operationId": "removeProjectFavourite",
            "summary": "Clear the caller's mark on this project",
            "description": "Idempotent: clearing a project that was never marked succeeds.",
            "responses": {
                "200": schemas.ok(
                    "The project is not marked.", schemas.json_of(schemas.ref("ProjectFavourite"))
                ),
                "404": schemas.NOT_FOUND,
                "409": schemas.failure("This instance serves no favourites store."),
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
    favourites: ProjectFavourites | None = None,
    clearances: ClearanceSummaries | None = None,
) -> Blueprint:
    bp = Blueprint("clearcut_projects", __name__)

    def caller() -> str:
        """The user whose favourites these are.

        `getattr` rather than `g.identity` because mock mode installs no
        identity boundary and still has to serve the screen (D36) -- the same
        fallback `drafts.py` and `documents.py` already use.
        """
        identity = getattr(g, "identity", None)
        return str(identity.user_id) if identity else "demo"

    def marked() -> set[str]:
        """The caller's marks, as candidates. Never a grant: every id is shown
        only against a project the route was already allowed to serve."""
        return favourites.favourites(caller()) if favourites is not None else set()

    def totals(project_ids: list[str]) -> dict[str, ClearanceSummary]:
        """The clearance summary of each id, in one call to the port.

        `project_ids` is exactly the set this request was already going to
        serve -- ids the caller is authorized to read, and no others. The
        totals are scoped by that argument and by nothing else: the port
        discovers no projects of its own, so there is no query here to widen
        and no workspace boundary to leak across.

        An id the store has no clearance work for reports zeroes rather than
        dropping out, because "nobody has analysed this yet" is the answer,
        and an absent key would be read as "totals unavailable" instead.
        """
        if clearances is None:
            return {}
        summaries = clearances.summaries_for_projects(project_ids)
        return {
            project_id: summaries.get(project_id, EMPTY_CLEARANCE_SUMMARY)
            for project_id in project_ids
        }

    @bp.route("/api/jurisdictions", methods=["GET"])
    def list_jurisdictions() -> ResponseReturnValue:
        return errors.run_use_case(
            lambda: [serializers.jurisdiction_json(jurisdiction) for jurisdiction in JURISDICTIONS]
        )

    @bp.route("/api/projects", methods=["GET"])
    def projects_index() -> ResponseReturnValue:
        def visible() -> list[JsonDict]:
            favourite_ids = marked()
            projects = (
                list_projects.execute()
                if access is None
                else [
                    access.get_project(project_id)
                    for project_id in sorted(access.visible_project_ids(g.identity.user_id))
                ]
            )
            clearance = totals([project.project_id for project in projects])
            return [
                serializers.project_json(
                    project,
                    favourite=project.project_id in favourite_ids,
                    clearance=clearance.get(project.project_id),
                )
                for project in projects
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
        optional_fields: tuple[tuple[str, frozenset[str] | None], ...] = (
            ("poster_uri", None),
            ("format", PROJECT_FORMATS),
            ("status", PROJECT_STATUSES),
        )
        for field, allowed in optional_fields:
            invalid = validators.reject_bad_optional(payload, field, allowed)
            if invalid is not None:
                return invalid
        poster_uri = validators.optional_text(payload, "poster_uri")
        project_format = validators.optional_text(payload, "format")
        status = validators.optional_text(payload, "status")
        project_id = validators.new_id()
        at = validators.now()

        organization_id = str(payload.get("organization_id", ""))
        if access is not None and (not organization_id or "/" in organization_id):
            return errors.error_response(400, "organization_id is required")

        def build() -> JsonDict:
            if access is not None:
                project = Project(
                    project_id, title, jurisdiction.code, at, poster_uri, project_format, status
                )
                access.create_project(g.identity.user_id, organization_id, project)
                return serializers.project_json(project)
            return serializers.project_json(
                create_project.execute(
                    project_id, title, jurisdiction, at, poster_uri, project_format, status
                )
            )

        return errors.run_use_case(build, status=201, location=f"/api/projects/{project_id}")

    @bp.route("/api/projects/<project_id>", methods=["GET"])
    def projects_show(project_id: str) -> ResponseReturnValue:
        return errors.run_use_case(
            lambda: serializers.project_json(
                access.get_project(project_id)
                if access is not None
                else get_project.execute(project_id),
                favourite=project_id in marked(),
            )
        )

    @bp.route("/api/projects/<project_id>/favourite", methods=["PUT", "DELETE"])
    def projects_favourite(project_id: str) -> ResponseReturnValue:
        """One route for both directions, because they are one fact with two
        values. `PUT`/`DELETE` rather than `POST` for the same reason: marking
        a project twice has to be marking it once."""
        if favourites is None:
            return errors.error_response(409, "favourites require a configured store")
        adding = request.method == "PUT"

        def build() -> JsonDict:
            if adding:
                favourites.add_favourite(caller(), project_id)
            else:
                favourites.remove_favourite(caller(), project_id)
            return {"project_id": project_id, "favourite": adding}

        return errors.run_use_case(build)

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
