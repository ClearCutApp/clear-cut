"""Authenticated workspace management; invitation links are human-shared only."""

import hashlib
import secrets
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from flask import Blueprint, Response, g
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import errors, schemas, validators
from clearcut.application.team_ports import ProductionSettings, WorkspaceManagement
from clearcut.domain.workspace import InvalidWorkspace, ProductionLocation, ProjectSettings

TAG = "Workspaces"
TAG_DESCRIPTION = (
    "Versioned team membership, invitations, private assignments and production locations."
)
SCHEMAS: dict[str, Any] = {}
_ORG = {"name": "organization_id", "in": "path", "required": True, "schema": {"type": "string"}}
_USER = {"name": "user_id", "in": "path", "required": True, "schema": {"type": "string"}}
_INVITE = {"name": "invitation_id", "in": "path", "required": True, "schema": {"type": "string"}}


def _operation(name: str, summary: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    result = {
        "tags": [TAG],
        "operationId": name,
        "summary": summary,
        "responses": {
            "200": schemas.ok("Authorized result.", schemas.json_of({"type": "object"})),
            "400": schemas.failure("Invalid input."),
            "403": schemas.failure("Workspace permission required."),
            "404": schemas.NOT_FOUND,
            "409": schemas.failure("Expected version changed."),
        },
    }
    if body is not None:
        result["requestBody"] = schemas.body(body)
    return result


_VERSION = {"type": "integer", "minimum": 1}
_TEXT = {"type": "string", "minLength": 1}
_ROLES = {"type": "string", "enum": ["owner", "admin", "producer", "writer", "viewer"]}
PATHS = {
    "/api/organizations/{organization_id}/members": {
        "parameters": [_ORG],
        "get": _operation("getWorkspaceMembers", "List members for workspace management"),
    },
    "/api/organizations/{organization_id}/members/{user_id}": {
        "parameters": [_ORG, _USER],
        "patch": _operation(
            "changeWorkspaceMember",
            "Change a member with last-owner protection",
            {
                "type": "object",
                "required": ["expected_version", "role", "active"],
                "properties": {
                    "expected_version": _VERSION,
                    "role": _ROLES,
                    "active": {"type": "boolean"},
                },
            },
        ),
    },
    "/api/organizations/{organization_id}/invitations": {
        "parameters": [_ORG],
        "get": _operation("getWorkspaceInvitations", "List invitation states without tokens"),
        "post": _operation(
            "createWorkspaceInvitation",
            "Create a seven-day verified-email invitation; no email is sent",
            {
                "type": "object",
                "required": ["email", "role"],
                "properties": {
                    "email": {"type": "string", "format": "email"},
                    "role": {"type": "string", "enum": ["admin", "producer", "writer", "viewer"]},
                },
            },
        ),
    },
    "/api/organizations/{organization_id}/invitations/{invitation_id}/revocation": {
        "parameters": [_ORG, _INVITE],
        "post": _operation(
            "revokeWorkspaceInvitation",
            "Revoke a pending invitation",
            {
                "type": "object",
                "required": ["expected_version"],
                "properties": {"expected_version": _VERSION},
            },
        ),
    },
    "/api/invitations/accept": {
        "post": _operation(
            "acceptWorkspaceInvitation",
            "Join a workspace without acquiring project access",
            {"type": "object", "required": ["token"], "properties": {"token": _TEXT}},
        )
    },
    "/api/projects/{project_id}/members": {
        "parameters": [schemas.PROJECT_ID],
        "get": _operation("getProjectMembers", "List active explicitly assigned project members"),
    },
    "/api/projects/{project_id}/members/{user_id}": {
        "parameters": [schemas.PROJECT_ID, _USER],
        "patch": _operation(
            "assignProjectMember",
            "Change private project access",
            {
                "type": "object",
                "required": ["expected_version", "role"],
                "properties": {
                    "expected_version": _VERSION,
                    "role": {
                        "type": ["string", "null"],
                        "enum": ["admin", "producer", "writer", "viewer", None],
                    },
                },
            },
        ),
    },
    "/api/projects/{project_id}/settings": {
        "parameters": [schemas.PROJECT_ID],
        "get": _operation("getProjectSettings", "Read production settings and selected locations"),
        "put": _operation(
            "saveProjectSettings",
            "Save expected-version production settings",
            {
                "type": "object",
                "required": ["expected_version", "title", "jurisdiction_code", "locations"],
                "properties": {
                    "expected_version": _VERSION,
                    "title": {"type": "string", "maxLength": 200},
                    "jurisdiction_code": {
                        "type": "string",
                        "enum": ["AR", "MX", "ES", "CO", "US", "CA"],
                    },
                    "locations": {
                        "type": "array",
                        "maxItems": 30,
                        "items": {
                            "type": "object",
                            "required": ["country", "location"],
                            "properties": {
                                "country": _TEXT,
                                "location": {"type": "string", "maxLength": 500},
                            },
                        },
                    },
                },
            },
        ),
    },
}


def _json(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value


def _expected(body: dict[str, Any]) -> int:
    version = body.get("expected_version")
    if type(version) is not int or version < 1:
        raise InvalidWorkspace("expected_version must be a positive integer")
    return int(version)


def create_workspaces_blueprint(
    teams: WorkspaceManagement | None, settings: ProductionSettings | None
) -> Blueprint:
    bp = Blueprint("clearcut_workspaces", __name__)

    @bp.after_request
    def private_response(response: Response) -> Response:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def unavailable() -> ResponseReturnValue:
        return errors.error_response(503, "workspace management is unavailable in this demo")

    @bp.get("/api/organizations/<organization_id>/members")
    def members(organization_id: str) -> ResponseReturnValue:
        if teams is None:
            return unavailable()
        return errors.run_use_case(
            lambda: {"members": _json(teams.members(g.identity.user_id, organization_id))}
        )

    @bp.get("/api/organizations/<organization_id>/invitations")
    def invitations(organization_id: str) -> ResponseReturnValue:
        if teams is None:
            return unavailable()
        return errors.run_use_case(
            lambda: {"invitations": _json(teams.invitations(g.identity.user_id, organization_id))}
        )

    @bp.post("/api/organizations/<organization_id>/invitations")
    def invite(organization_id: str) -> ResponseReturnValue:
        if teams is None:
            return unavailable()

        def build() -> dict[str, Any]:
            body = validators.json_body()
            token = secrets.token_urlsafe(32)
            value = teams.invite(
                g.identity.user_id,
                organization_id,
                validators.new_id(),
                hashlib.sha256(token.encode()).hexdigest(),
                body.get("email", ""),
                body.get("role", ""),
                datetime.now(UTC),
            )
            return {"invitation": _json(value), "token": token}

        return errors.run_use_case(build)

    @bp.post("/api/invitations/accept")
    def accept() -> ResponseReturnValue:
        if teams is None:
            return unavailable()

        def build() -> dict[str, Any]:
            token = validators.json_body().get("token")
            if not isinstance(token, str) or not 32 <= len(token) <= 256:
                raise InvalidWorkspace("invalid invitation token")
            organization = teams.accept(
                g.identity, hashlib.sha256(token.encode()).hexdigest(), datetime.now(UTC)
            )
            return {"organization_id": organization}

        return errors.run_use_case(build)

    @bp.post("/api/organizations/<organization_id>/invitations/<invitation_id>/revocation")
    def revoke(organization_id: str, invitation_id: str) -> ResponseReturnValue:
        if teams is None:
            return unavailable()

        def build() -> dict[str, Any]:
            teams.revoke_invitation(
                g.identity.user_id,
                organization_id,
                invitation_id,
                _expected(validators.json_body()),
                datetime.now(UTC),
            )
            return {"revoked": True}

        return errors.run_use_case(build)

    @bp.patch("/api/organizations/<organization_id>/members/<user_id>")
    def change(organization_id: str, user_id: str) -> ResponseReturnValue:
        if teams is None:
            return unavailable()

        def build() -> dict[str, Any]:
            body = validators.json_body()
            active = body.get("active")
            if type(active) is not bool:
                raise InvalidWorkspace("active must be a boolean")
            teams.change_member(
                g.identity.user_id,
                organization_id,
                user_id,
                body.get("role", ""),
                active,
                _expected(body),
                datetime.now(UTC),
            )
            return {"updated": True}

        return errors.run_use_case(build)

    @bp.get("/api/projects/<project_id>/members")
    def assigned(project_id: str) -> ResponseReturnValue:
        if teams is None:
            return unavailable()
        return errors.run_use_case(lambda: teams.project_members(g.identity.user_id, project_id))

    @bp.patch("/api/projects/<project_id>/members/<user_id>")
    def assign(project_id: str, user_id: str) -> ResponseReturnValue:
        if teams is None:
            return unavailable()

        def build() -> dict[str, Any]:
            body = validators.json_body()
            if "role" not in body:
                raise InvalidWorkspace("role or null is required")
            teams.assign(
                g.identity.user_id,
                project_id,
                user_id,
                body["role"],
                _expected(body),
                datetime.now(UTC),
            )
            return {"updated": True}

        return errors.run_use_case(build)

    @bp.get("/api/projects/<project_id>/settings")
    def get_settings(project_id: str) -> ResponseReturnValue:
        if settings is None:
            return unavailable()
        return errors.run_use_case(lambda: asdict(settings.get(project_id)))

    @bp.put("/api/projects/<project_id>/settings")
    def save_settings(project_id: str) -> ResponseReturnValue:
        if settings is None:
            return unavailable()

        def build() -> dict[str, Any]:
            body = validators.json_body()
            version = _expected(body)
            values = body.get("locations")
            if (
                not isinstance(body.get("title"), str)
                or not isinstance(values, list)
                or any(
                    not isinstance(value, dict) or set(value) != {"country", "location"}
                    for value in values
                )
            ):
                raise InvalidWorkspace("provide a title and country/location pairs")
            value = ProjectSettings(
                project_id,
                body["title"],
                body.get("jurisdiction_code", ""),
                version + 1,
                tuple(ProductionLocation(**location) for location in values),
            )
            return asdict(settings.save(g.identity.user_id, value, version, datetime.now(UTC)))

        return errors.run_use_case(build)

    return bp
