"""The analytics reader cannot broaden a private project's authorization."""

from types import SimpleNamespace

from flask import Flask

from clearcut.adapters.http.activity import create_activity_blueprint
from clearcut.adapters.http.identity import install_identity_boundary
from clearcut.domain.activity import activity_envelope, read_event
from tests.unit.adapters.test_durable_jobs import NOW
from tests.unit.adapters.test_identity_boundary import Access, Verifier


def test_activity_queries_are_scoped_by_server_identity_and_bad_cursors_are_rejected():
    event = read_event(
        activity_envelope(
            "event",
            "organization-one",
            "one",
            "revision_saved",
            NOW,
            2,
            {"revision_id": "revision-2"},
        )
    )
    calls = []

    def events(organization_id, project_id, before):
        calls.append((organization_id, project_id, before))
        return [event]

    app = Flask(__name__)
    install_identity_boundary(app, Verifier(), Access())
    app.register_blueprint(
        create_activity_blueprint(
            SimpleNamespace(list=events, trends=lambda organization, project: [])
        )
    )
    client = app.test_client()
    path = "/api/projects/one/activity"
    assert client.get(path, headers={"Authorization": "Bearer bob"}).status_code == 404
    assert calls == []
    response = client.get(path, headers={"Authorization": "Bearer viewer"})
    assert response.status_code == 200
    assert calls == [("organization-one", "one", None)]
    assert response.get_json()["events"][0]["event_id"] == "event"
    assert (
        client.get(path + "?before=invalid", headers={"Authorization": "Bearer viewer"}).status_code
        == 400
    )
