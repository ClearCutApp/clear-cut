"""The live HTTP boundary queues immutable revisions without invoking providers."""

from typing import Any, cast

from flask import Flask, g

from clearcut.adapters.gcp.drafts import FirestoreDraftStore
from clearcut.adapters.http.scripts import create_scripts_blueprint
from clearcut.domain.identity import Identity
from tests.unit.adapters.test_durable_jobs import configured


def test_revision_queue_poll_and_cancel_require_no_process_local_runner():
    store, jobs, _, _ = configured()
    app = Flask(__name__)

    @app.before_request
    def identity() -> None:
        g.identity = Identity("writer", "writer@example.invalid")
        g.organization_id = "org"

    app.register_blueprint(
        create_scripts_blueprint(
            cast(Any, None),
            cast(Any, None),
            cast(Any, None),
            cast(Any, None),
            cast(Any, None),
            durable_jobs=jobs,
            drafts=FirestoreDraftStore(store),
        )
    )
    client = app.test_client()
    path = "/api/projects/project/scripts"
    assert (
        client.post(
            path, json={"gcs_uri": "gs://foreign/file", "jurisdiction_code": "AR"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            path, json={"revision_id": "foreign-revision", "jurisdiction_code": "AR"}
        ).status_code
        == 404
    )
    response = client.post(path, json={"revision_id": "revision-1", "jurisdiction_code": "AR"})
    assert response.status_code == 202
    body = response.get_json()
    assert body["state"] == "QUEUED" and body["revision_id"] == "revision-1"
    assert "analysis_launches/" + body["analysis_id"] in store.data
    assert jobs.load(body["analysis_id"]).attempt == 0
    assert client.get(response.headers["Location"]).get_json()["stage"] == "queued"
    assert (
        client.get("/api/projects/project/analyses/current").get_json()["analysis_id"]
        == body["analysis_id"]
    )
    assert (
        client.post(path, json={"revision_id": "revision-1", "jurisdiction_code": "AR"}).status_code
        == 409
    )
    cancelled = client.post(response.headers["Location"] + "/cancellation")
    assert cancelled.status_code == 200 and cancelled.get_json()["state"] == "CANCELLED"
