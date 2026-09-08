import json
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from infra.deployed_acceptance import (
    REQUIRED_PATHS,
    STEPS,
    Acceptance,
    Response,
    canonical,
    digest,
    synthetic_pdf,
)
from reportlab.pdfgen.canvas import Canvas

from clearcut.domain.screenplay import encode_document

TARGET = "https://acceptance.example"
DOCUMENT = {
    "type": "doc",
    "content": [
        {
            "type": "paragraph",
            "attrs": {"blockId": "b1", "sceneId": "s1", "kind": "scene-heading"},
            "content": [{"type": "text", "text": "INT. RECORD STORE - NIGHT"}],
        },
        {
            "type": "paragraph",
            "attrs": {"blockId": "b2", "sceneId": "s1", "kind": "action"},
            "content": [{"type": "text", "text": "A Coca-Cola bottle."}],
        },
    ],
}


def response(value: Any, status: int = 200) -> Response:
    return Response(status, canonical(value))


class Service:
    """Protocol fixture asserts requests; it never invokes real providers."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.calls: list[tuple[str, str]] = []
        self.actor = "actor-1"
        self.obsolete = False
        self.denied = False
        self.lost = False
        self.pending = False
        self.document = DOCUMENT
        self.version = 0
        self.item_version = 1
        self.item_state = "BLOCKED"
        self.item_evidence: list[str] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        body: dict[str, Any] | None = None,
        file: bytes | None = None,
    ) -> Response:
        self.calls.append((method, path))
        if method != "GET":
            receipt = json.loads((self.directory / "receipt.json").read_bytes())
            assert receipt["intent"]["method"] == method
            assert receipt["intent"]["path"] == path
            assert receipt["intent"]["request_sha256"] == digest(canonical(body))
            if self.lost:
                self.lost = False
                raise TimeoutError("sensitive provider response must never be persisted")
        if path == "/api/health":
            return response({"mode": "live"})
        if path == "/api/client-config":
            return response(dict.fromkeys(("apiKey", "authDomain", "projectId", "appId"), "app"))
        if path == "/api/openapi.json":
            paths: dict[str, Any] = dict.fromkeys(REQUIRED_PATHS, {}) if not self.obsolete else {}
            paths["/api/projects/{project_id}/scripts"] = {"post": {"responses": {"202": {}}}}
            return response({"paths": paths})
        if path == "/api/me":
            return response({"user_id": self.actor}, 401 if self.denied else 200)
        if path == "/api/projects" and not authenticated:
            return response({}, 401)
        if path == "/api/organizations":
            assert body == {"name": "Acceptance run-1"}
            return response({"organization_id": "org-1"}, 201)
        if path == "/api/projects":
            assert body == {
                "title": "Synthetic acceptance run-1",
                "organization_id": "org-1",
                "jurisdiction_code": "AR",
            }
            return response({"project_id": "project-1"}, 201)
        assert path.startswith("/api/projects/project-1/")
        suffix = path.removeprefix("/api/projects/project-1/")
        if suffix == "imports":
            assert body == {"expected_version": "0"} and file == synthetic_pdf("run-1")
            self.version = 1
            return response(
                {
                    "draft": {"project_id": "project-1", "version": 1, "document": self.document},
                    "original": {"file_id": "original-1"},
                },
                201,
            )
        if suffix == "draft":
            if method == "PUT":
                assert body is not None
                if body["expected_version"] != self.version:
                    return response({"current_version": self.version}, 409)
                self.document, self.version = body["document"], self.version + 1
            return response({"version": self.version, "document": self.document})
        if suffix == "revisions":
            assert body == {"expected_version": 2}
            return response(
                {
                    "revision_id": "revision-1",
                    "draft_version": 2,
                    "sha256": digest(encode_document(self.document)),
                },
                201,
            )
        if suffix == "revisions/revision-1":
            return response(
                {
                    "draft_version": 2,
                    "revision_id": "revision-1",
                    "document": self.document,
                    "sha256": digest(encode_document(self.document)),
                }
            )
        job = {
            "analysis_id": "analysis-1",
            "script_id": "script-1",
            "project_id": "project-1",
            "revision_id": "revision-1",
        }
        if suffix == "scripts":
            assert body == {"revision_id": "revision-1", "jurisdiction_code": "AR"}
            return response({**job, "state": "QUEUED"}, 202)
        if suffix == "analyses/analysis-1":
            return response({**job, "state": "RUNNING" if self.pending else "SUCCEEDED"})
        if suffix == "scripts/script-1":
            return response(
                {
                    "revision_id": "revision-1",
                    "revision_draft_version": 2,
                    "findings": [{"finding_id": "item-1"}],
                    "scene_anchors": {"s1": {}},
                    "clearance_bindings": {
                        "item-1": {"present": True, "revision_id": "revision-1"}
                    },
                }
            )
        item = {
            "item_id": "item-1",
            "state": self.item_state,
            "version": self.item_version,
            "needs_review": False,
            "evidence_file_ids": self.item_evidence,
        }
        if suffix == "tracker-items":
            return response([item])
        if suffix == "documents":
            assert file == synthetic_pdf("run-1")
            return response({"file_id": "evidence-1", "sha256": digest(file)}, 201)
        if suffix == "documents/evidence-1":
            return Response(200, synthetic_pdf("run-1"), "application/pdf")
        if suffix.startswith("tracker-items/item-1"):
            if method == "GET":
                return response(item)
            assert body is not None and body["expected_version"] == self.item_version
            self.item_version += 1
            if suffix.endswith("details"):
                assert set(body) == {
                    "expected_version",
                    "note",
                    "clearance_conditions",
                    "due_date",
                    "assignee_id",
                    "evidence_file_ids",
                    "draft_email",
                }
                self.item_evidence = body["evidence_file_ids"]
            elif method == "PATCH":
                assert body["state"] == "CLEARED"
                self.item_state = "CLEARED"
            else:
                assert body["revision_id"] == "revision-1" and body["acknowledged"] is True
            return response(
                {
                    **item,
                    "state": self.item_state,
                    "version": self.item_version,
                    "evidence_file_ids": self.item_evidence,
                }
            )
        selection = {
            "analysis_id": "analysis-1",
            "revision_id": "revision-1",
            "expected_generation": "generation-1",
            "expected_epoch": 3,
        }
        counts = {"confirmed_cleared": 1, "total_retained": 1}
        if suffix == "reports/context":
            return response({"configured": True, "snapshot": {**selection, "counts": counts}})
        if suffix == "reports":
            assert body == {**selection, "language": "en"}
            return response(
                {
                    "report_id": "report-1",
                    "revision_id": "revision-1",
                    "counts": counts,
                    "analysis_id": "analysis-1",
                    "generation_id": "generation-1",
                    "clearance_epoch": 3,
                },
                201,
            )
        if suffix.endswith("format=pdf"):
            output = BytesIO()
            canvas = Canvas(output)
            canvas.drawString(72, 700, "item-1 report-1 revision-1")
            canvas.save()
            return Response(200, output.getvalue(), "application/pdf")
        if suffix.endswith("format=csv"):
            return Response(
                200,
                b"report_id,report_revision,item_id,evidence_ids,state\n"
                b"report-1,revision-1,item-1,evidence-1,CLEARED\n",
                "text/csv",
            )
        raise AssertionError("unexpected route")


def test_resumes_complete_protocol_without_repeating_writes(tmp_path):
    service = Service(tmp_path)
    first = Acceptance(TARGET, "run-1", tmp_path, service).advance(8)
    assert first["status"] == "pending" and first["next_step"] == "enqueue"
    second = Acceptance(TARGET, "run-1", tmp_path, service).advance(32)
    assert second["status"] == "success" and second["completed_steps"] == len(STEPS)
    assert service.calls.count(("POST", "/api/organizations")) == 1
    assert service.calls.count(("POST", "/api/projects/project-1/scripts")) == 1
    receipt = (tmp_path / "receipt.json").read_text()
    assert "Coca-Cola" not in receipt and "actor-1" not in receipt
    state = json.loads(receipt)
    assert state["evidence"]["pdf_bytes"] > 0 and state["evidence"]["csv_bytes"] > 0
    assert not (tmp_path / "receipt.json").stat().st_mode & 0o077


def test_lost_mutation_ack_and_crash_intent_never_repost(tmp_path):
    service = Service(tmp_path)
    service.lost = True
    result = Acceptance(TARGET, "run-1", tmp_path, service).advance()
    assert result["status"] == "unknown"
    assert "sensitive" not in (tmp_path / "receipt.json").read_text()
    state = json.loads((tmp_path / "receipt.json").read_text())
    state["status"] = "pending"
    (tmp_path / "receipt.json").write_text(json.dumps(state))
    result = Acceptance(TARGET, "run-1", tmp_path, service).advance()
    assert result["status"] == "unknown"
    assert service.calls.count(("POST", "/api/organizations")) == 1


def test_polling_budget_reuses_job_across_invocations(tmp_path):
    service = Service(tmp_path)
    service.pending = True
    result = Acceptance(TARGET, "run-1", tmp_path, service).advance(32)
    assert result["status"] == "pending" and result["next_step"] == "poll"
    result = Acceptance(TARGET, "run-1", tmp_path, service).advance(32)
    assert result["status"] == "pending"
    assert service.calls.count(("GET", "/api/projects/project-1/analyses/analysis-1")) == 2
    assert service.calls.count(("POST", "/api/projects/project-1/scripts")) == 1
    service.pending = False
    assert Acceptance(TARGET, "run-1", tmp_path, service).advance(32)["status"] == "success"


@pytest.mark.parametrize("change", ["actor", "target", "run"])
def test_receipt_cannot_be_rebound(tmp_path, change):
    service = Service(tmp_path)
    Acceptance(TARGET, "run-1", tmp_path, service).advance(1)
    writes = [call for call in service.calls if call[0] != "GET"]
    if change == "actor":
        service.actor = "another-actor"
    with pytest.raises(ValueError, match="receipt_binding_changed"):
        Acceptance(
            "https://other.example" if change == "target" else TARGET,
            "run-2" if change == "run" else "run-1",
            tmp_path,
            service,
        ).advance()
    assert [call for call in service.calls if call[0] != "GET"] == writes


@pytest.mark.parametrize("failure", ["obsolete", "denied"])
def test_preflight_rejects_obsolete_or_unauthenticated_service(tmp_path, failure):
    service = Service(tmp_path)
    setattr(service, failure, True)
    with pytest.raises(ValueError):
        Acceptance(TARGET, "run-1", tmp_path, service).advance()
    assert all(method == "GET" for method, _ in service.calls)
    assert not (tmp_path / "receipt.json").exists()


def test_acceptance_import_edit_cas_revision_against_real_flask_routes(tmp_path):
    from flask import Flask

    from clearcut.adapters.demo.documents import MemoryProjectDocuments
    from clearcut.adapters.demo.drafts import MemoryDraftStore, MemoryScreenplayContent
    from clearcut.adapters.documents.screenplay_export import screenplay_fdx, screenplay_pdf
    from clearcut.adapters.documents.screenplay_import import ScreenplayImporter
    from clearcut.adapters.http.documents import create_documents_blueprint
    from clearcut.adapters.http.drafts import create_drafts_blueprint

    app = Flask(__name__)
    drafts, content, documents = (
        MemoryDraftStore(),
        MemoryScreenplayContent(),
        MemoryProjectDocuments(),
    )
    app.register_blueprint(create_drafts_blueprint(drafts, content))
    app.register_blueprint(
        create_documents_blueprint(
            documents, drafts, content, ScreenplayImporter(), screenplay_pdf, screenplay_fdx
        )
    )
    client = app.test_client()

    class FlaskService(Service):
        def request(self, method, path, *, authenticated=True, body=None, file=None):
            if path.startswith("/api/projects/project-1/"):
                kwargs: dict[str, Any] = {
                    "data": json.dumps(body),
                    "content_type": "application/json",
                }
                if file is not None:
                    kwargs = {
                        "data": {**(body or {}), "file": (BytesIO(file), "fixture.pdf")},
                        "content_type": "multipart/form-data",
                    }
                result = client.open(path, method=method, **kwargs)
                return Response(result.status_code, result.data, result.content_type)
            return super().request(method, path, authenticated=authenticated, body=body, file=file)

    run = Acceptance(TARGET, "run-1", tmp_path, FlaskService(tmp_path))
    result = run.advance(8)
    assert result["next_step"] == "enqueue" and result["status"] == "pending"
    receipt = json.loads((tmp_path / "receipt.json").read_text())
    revision_id = receipt["resources"]["revision_id"]
    revision = client.get("/api/projects/project-1/revisions/" + revision_id).json
    assert revision is not None
    assert revision["draft_version"] == 2
    assert revision["document"]["content"][-1]["content"][0]["text"] == "The radio falls silent."
    original = client.get(
        "/api/projects/project-1/documents/" + receipt["resources"]["original_file_id"]
    )
    assert original.data == synthetic_pdf("run-1")


def test_changed_revision_hash_stops_before_analysis(tmp_path):
    class CorruptRevision(Service):
        def request(self, method, path, **kwargs):
            result = super().request(method, path, **kwargs)
            if path.endswith("revisions/revision-1"):
                return response({**result.json(), "sha256": "0" * 64})
            return result

    service = CorruptRevision(tmp_path)
    result = Acceptance(TARGET, "run-1", tmp_path, service).advance(32)
    assert result["status"] == "failed"
    assert ("POST", "/api/projects/project-1/scripts") not in service.calls
