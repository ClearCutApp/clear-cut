"""Real route and identity boundaries for server-created invitation tokens."""

from flask import Flask

from clearcut.adapters.http.identity import install_identity_boundary
from clearcut.adapters.http.workspaces import create_workspaces_blueprint
from tests.unit.adapters.test_identity_boundary import Verifier
from tests.unit.adapters.test_teams import configured


def test_workspace_routes_never_send_invites_and_hide_token_hashes():
    store, teams, access = configured()
    store.data["organizations/org/members/alice"] = {"active": True, "role": "owner", "version": 1}
    app = Flask(__name__)
    install_identity_boundary(app, Verifier(), access)
    app.register_blueprint(create_workspaces_blueprint(teams, None))
    client = app.test_client()
    path = "/api/organizations/org/invitations"
    payload = {"email": "writer@example.com", "role": "writer"}
    assert (
        client.post(path, json=payload, headers={"Authorization": "Bearer writer"}).status_code
        == 403
    )
    created = client.post(path, json=payload, headers={"Authorization": "Bearer alice"})
    assert created.status_code == 200 and created.headers["Cache-Control"] == "no-store"
    body = created.get_json()
    assert len(body["token"]) >= 32 and "token_hash" not in body["invitation"]
    assert all(body["token"] not in str(value) for value in store.data.values())
    accepted = client.post(
        "/api/invitations/accept",
        json={"token": body["token"]},
        headers={"Authorization": "Bearer writer"},
    )
    assert accepted.status_code == 200 and accepted.json == {"organization_id": "org"}
    assert "users/writer/projects/project" not in store.data
    assert (
        client.patch(
            "/api/organizations/org/members/writer",
            json={"expected_version": True, "role": "viewer", "active": True},
            headers={"Authorization": "Bearer alice"},
        ).status_code
        == 400
    )
