"""Report resources remain project-private and exports use saved bytes."""

from dataclasses import replace
from types import SimpleNamespace
from typing import Any, cast

from flask import Flask

from clearcut.adapters.http.identity import install_identity_boundary
from clearcut.adapters.http.reports import create_reports_blueprint
from clearcut.application.create_report import CreateReport
from tests.unit.adapters.test_identity_boundary import Access, Verifier
from tests.unit.adapters.test_reports import ready_report


def test_report_http_identity_permissions_validation_and_immutable_download():
    _, _, value = ready_report()
    value = replace(value, project_id="one", organization_id="organization-one")
    calls: list[dict[str, Any]] = []

    def execute(**kwargs: Any):
        calls.append(kwargs)
        return value

    app = Flask(__name__)
    install_identity_boundary(app, Verifier(), Access())
    app.register_blueprint(
        create_reports_blueprint(
            SimpleNamespace(
                list=lambda project, before: [value], get=lambda project, report: value
            ),
            cast(CreateReport, SimpleNamespace(execute=execute)),
            None,
            SimpleNamespace(get_bytes=lambda reference: b"immutable PDF bytes"),
            lambda project: "Title",
        )
    )
    client = app.test_client()
    path = "/api/projects/one/reports"
    payload = {
        "analysis_id": "analysis",
        "revision_id": "revision-1",
        "expected_generation": "generation",
        "expected_epoch": 2,
        "language": "es",
    }
    for user in ("bob", "writer", "viewer"):
        assert (
            client.post(path, json=payload, headers={"Authorization": "Bearer " + user}).status_code
            == 404
        )
    assert calls == []
    headers = {"Authorization": "Bearer alice"}
    assert (
        client.post(path, json={**payload, "expected_epoch": True}, headers=headers).status_code
        == 400
    )
    assert client.post(path, json={**payload, "language": "fr"}, headers=headers).status_code == 400
    response = client.post(path, json=payload, headers=headers)
    assert response.status_code == 201
    assert calls[0]["organization_id"] == "organization-one" and calls[0]["actor"] == "alice"
    body = response.get_json()
    assert "snapshot" not in body and "analysis_manifest" not in body
    assert client.get(path, headers={"Authorization": "Bearer viewer"}).status_code == 200
    download = client.get(path + "/report/download?format=pdf", headers=headers)
    assert download.status_code == 200 and download.data == b"immutable PDF bytes"
    assert download.headers["Cache-Control"] == "no-store"
    assert (
        client.get(path + "/report/download", headers={"Authorization": "Bearer bob"}).status_code
        == 404
    )
