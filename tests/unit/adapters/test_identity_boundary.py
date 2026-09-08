"""Exercise the HTTP boundary with two unrelated organizations."""

import pytest
from flask import Flask

from clearcut.adapters.http.identity import install_identity_boundary
from clearcut.adapters.http.system import create_system_blueprint
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.identity import AccessDenied, AuthenticationRequired, Identity, permits
from clearcut.domain.project import Project


class Verifier:
    def verify(self, token: str) -> Identity:
        if token == "down":
            raise SourceUnavailable("private provider details")
        if token not in {"alice", "bob", "writer", "viewer"}:
            raise AuthenticationRequired("sign in again")
        return Identity(token, token + "@example.com")


class Access:
    def authorize(self, user_id: str, project_id: str, action: str) -> str:
        roles = {
            ("alice", "one"): "producer",
            ("bob", "two"): "producer",
            ("writer", "one"): "writer",
            ("viewer", "one"): "viewer",
        }
        if not permits(roles.get((user_id, project_id), ""), action):
            raise AccessDenied("private details")
        return "organization-" + project_id

    def visible_project_ids(self, user_id: str) -> set[str]:
        return {"one"} if user_id == "alice" else {"two"}

    def get_project(self, project_id: str) -> Project:
        return Project(project_id, "Private script", "AR", "2026-09-06T12:00:00Z")

    def create_project(self, user_id: str, organization_id: str, project: Project) -> None:
        raise AccessDenied("not assigned")

    def create_organization(self, user_id: str, organization_id: str, name: str) -> None:
        pass

    def organizations(self, user_id: str) -> list[dict[str, str]]:
        return []


@pytest.fixture
def client():
    app = Flask(__name__)
    install_identity_boundary(app, Verifier(), Access())
    app.add_url_rule(
        "/api/projects/<project_id>/script-files",
        "files",
        lambda project_id: {"secret": project_id},
        methods=["GET", "POST"],
    )
    app.add_url_rule(
        "/api/projects/<project_id>/bible",
        "bible",
        lambda project_id: {"secret": project_id},
        methods=["POST"],
    )
    for suffix in ("draft", "revisions", "transcriptions"):
        app.add_url_rule(
            "/api/projects/<project_id>/" + suffix,
            suffix,
            lambda project_id: {"project": project_id},
            methods=["PUT", "POST"],
        )
    app.register_blueprint(create_system_blueprint("live", lambda: {}))
    return app.test_client()


def test_health_is_public_but_private_data_needs_identity(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/projects/one/script-files").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer expired"}).status_code == 401


@pytest.mark.parametrize("user,project", [("alice", "two"), ("bob", "one")])
def test_two_organizations_cannot_read_each_others_files(client, user, project):
    response = client.get(
        f"/api/projects/{project}/script-files", headers={"Authorization": "Bearer " + user}
    )
    assert response.status_code == 404
    assert response.json == {"error": "project not found"}


def test_assigned_producer_can_read_and_upload(client):
    for method in [client.get, client.post]:
        assert (
            method(
                "/api/projects/one/script-files", headers={"Authorization": "Bearer alice"}
            ).status_code
            == 200
        )


def test_writer_can_edit_bible_but_viewer_cannot(client):
    assert (
        client.post(
            "/api/projects/one/bible", headers={"Authorization": "Bearer writer"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/projects/one/bible", headers={"Authorization": "Bearer viewer"}
        ).status_code
        == 404
    )


def test_identity_outage_fails_closed_without_leaking_provider_details(client):
    response = client.get("/api/me", headers={"Authorization": "Bearer down"})
    assert response.status_code == 503
    assert "private" not in response.get_data(as_text=True)


def test_identity_context_contains_only_verified_identity(client):
    response = client.get("/api/me", headers={"Authorization": "Bearer alice"})
    assert response.json == {"user_id": "alice", "email": "alice@example.com"}


def test_public_client_configuration_contains_only_explicit_public_fields():
    app = Flask(__name__)
    install_identity_boundary(app, Verifier(), Access())
    config = {
        "apiKey": "public-key",
        "authDomain": "test.firebaseapp.com",
        "projectId": "test",
        "appId": "web-app",
    }
    app.register_blueprint(create_system_blueprint("live", lambda: {}, config))
    assert app.test_client().get("/api/client-config").json == config


@pytest.mark.parametrize("suffix,method", [("draft", "PUT"), ("revisions", "POST")])
def test_writer_saves_drafts_and_revisions_but_viewer_cannot(client, suffix, method):
    for user, expected in [("writer", 200), ("viewer", 404), ("bob", 404)]:
        assert (
            client.open(
                "/api/projects/one/" + suffix,
                method=method,
                headers={"Authorization": "Bearer " + user},
            ).status_code
            == expected
        )


def test_viewer_can_transcribe_only_in_assigned_project(client):
    assert (
        client.post(
            "/api/projects/one/transcriptions", headers={"Authorization": "Bearer viewer"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/projects/two/transcriptions", headers={"Authorization": "Bearer viewer"}
        ).status_code
        == 404
    )
