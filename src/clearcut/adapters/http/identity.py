"""Fail-closed identity and private-project boundary for the existing API."""

from flask import Flask, g, request
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import errors
from clearcut.application.workspace_ports import IdentityVerifier, ProjectAccess
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.identity import AccessDenied, AuthenticationRequired

_PUBLIC = frozenset(
    {"/api/client-config", "/api/health", "/api/jurisdictions", "/api/openapi.json", "/api/docs"}
)


def install_identity_boundary(
    app: Flask,
    verifier: IdentityVerifier,
    access: ProjectAccess,
) -> None:
    @app.before_request
    def authenticate() -> ResponseReturnValue | None:
        if not request.path.startswith("/api/") or request.path in _PUBLIC:
            return None
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return errors.error_response(401, "sign in required")
        try:
            g.identity = verifier.verify(token)
            project_id = (request.view_args or {}).get("project_id")
            if project_id:
                action = "read"
                if request.method not in {"GET", "HEAD", "OPTIONS"}:
                    # `/favourite` is a read action although it writes: what it
                    # writes belongs to the caller, not to the project, so
                    # anyone who may open the project may bookmark it. A viewer
                    # who could not would be a viewer with no list of their own.
                    if request.path.endswith(
                        ("/questions", "/transcriptions", "/search", "/favourite")
                    ) or ("/notifications/" in request.path and request.path.endswith("/read")):
                        action = "read"
                    elif request.path.endswith(
                        (
                            "/script-files",
                            "/scripts",
                            "/draft",
                            "/revisions",
                            "/imports",
                            "/cancellation",
                        )
                    ):
                        action = "script"
                    else:
                        action = "write" if "/bible" in request.path else "produce"
                g.organization_id = access.authorize(g.identity.user_id, project_id, action)
        except AuthenticationRequired as exc:
            return errors.error_response(401, str(exc))
        except AccessDenied:
            return errors.error_response(404, "project not found")
        except SourceUnavailable:
            return errors.error_response(503, "identity or workspace service unavailable")
        return None
