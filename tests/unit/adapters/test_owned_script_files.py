"""A live-style route resolves only server-registered project-owned files."""

from io import BytesIO
from typing import Any, cast

from flask import Flask
from flask.testing import FlaskClient

from clearcut.adapters.http.scripts import create_scripts_blueprint
from clearcut.application.upload_script_file import UploadScriptFile
from clearcut.domain.errors import RecordNotFound


class Storage:
    def store(self, project_id: str, filename: str, content: bytes) -> str:
        return "gs://private-bucket/immutable-object"


class Files:
    def __init__(self) -> None:
        self.files: dict[tuple[str, str], str] = {}

    def register_file(self, project_id: str, file_id: str, uri: str) -> None:
        self.files[(project_id, file_id)] = uri

    def resolve_file(self, project_id: str, file_id: str) -> str:
        if (project_id, file_id) not in self.files:
            raise RecordNotFound("file not found")
        return self.files[(project_id, file_id)]


class Analysis:
    def __init__(self) -> None:
        self.called = False

    def execute(self, *args):
        self.called = True
        raise RuntimeError("analysis execution is outside this boundary test")


def client() -> tuple[FlaskClient, Files, Analysis]:
    app = Flask(__name__)
    files = Files()
    analysis = Analysis()
    app.register_blueprint(
        create_scripts_blueprint(
            UploadScriptFile(Storage()),
            cast(Any, None),
            cast(Any, None),
            cast(Any, analysis),
            cast(Any, None),
            files,
        )
    )
    return app.test_client(), files, analysis


def test_upload_returns_owned_file_id_registered_for_its_project():
    http, files, _ = client()
    response = http.post(
        "/api/projects/one/script-files",
        data={"file": (BytesIO(b"%PDF-test"), "draft.pdf", "application/pdf")},
    )
    assert response.status_code == 201
    body = response.get_json()
    assert isinstance(body, dict)
    assert files.resolve_file("one", body["file_id"]) == body["gcs_uri"]


def test_browser_supplied_storage_uri_cannot_start_live_analysis():
    http, _, analysis = client()
    response = http.post(
        "/api/projects/one/scripts",
        json={"gcs_uri": "gs://other-tenant/private.pdf", "version": 1, "jurisdiction_code": "AR"},
    )
    assert response.status_code == 400
    assert not analysis.called


def test_another_projects_file_id_cannot_start_analysis():
    http, files, analysis = client()
    files.register_file("two", "owned-file", "gs://other-tenant/private.pdf")
    response = http.post(
        "/api/projects/one/scripts",
        json={"file_id": "owned-file", "version": 1, "jurisdiction_code": "AR"},
    )
    assert response.status_code == 404
    assert not analysis.called
