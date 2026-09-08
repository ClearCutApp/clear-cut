"""Owned project documents, safe screenplay import and immutable revision exports."""

from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from uuid import uuid4

from flask import Blueprint, Response, g, request, send_file
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import documents_spec, errors
from clearcut.application.document_ports import ProjectDocuments, ScreenplayImport
from clearcut.application.draft_ports import DraftStore, ScreenplayContent
from clearcut.application.screenplay_drafts import read_document, save_draft
from clearcut.domain.document import InvalidDocument, ProjectDocument
from clearcut.domain.screenplay import Draft

TAG = "Documents"
TAG_DESCRIPTION = "Owned immutable originals, evidence and saved-revision screenplay downloads."
SCHEMAS = documents_spec.SCHEMAS
PATHS = documents_spec.PATHS


def document_json(document: ProjectDocument) -> dict[str, Any]:
    data = asdict(document)
    del data["storage_uri"]
    return data


def create_documents_blueprint(
    documents: ProjectDocuments,
    drafts: DraftStore,
    content: ScreenplayContent,
    importer: ScreenplayImport,
    screenplay_pdf: Callable[[dict[str, Any], str, str], bytes],
    screenplay_fdx: Callable[[dict[str, Any]], bytes],
) -> Blueprint:
    bp = Blueprint("clearcut_documents", __name__)

    @bp.errorhandler(413)
    def oversized(error: Any) -> ResponseReturnValue:
        return errors.error_response(413, "file exceeds 25 MiB")

    def actor() -> str:
        identity = getattr(g, "identity", None)
        return identity.user_id if identity else "demo"

    def upload(kind: str, project_id: str) -> ProjectDocument:
        request.max_content_length = 25 * 1024 * 1024 + 65536
        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename:
            raise InvalidDocument("file is required")
        data = uploaded.read(25 * 1024 * 1024 + 1)
        if not data or len(data) > 25 * 1024 * 1024:
            raise InvalidDocument("file must contain 1 byte to 25 MiB")
        return documents.put(
            getattr(g, "organization_id", "demo"),
            project_id,
            uploaded.filename,
            uploaded.mimetype or "application/octet-stream",
            data,
            kind,
            actor(),
            datetime.now(UTC).isoformat(),
        )

    @bp.get("/api/projects/<project_id>/documents")
    def index(project_id: str) -> ResponseReturnValue:
        def build() -> dict[str, Any]:
            items = documents.list(project_id, request.args.get("before"))
            return {
                "documents": [document_json(item) for item in items],
                "next_before": items[-1].file_id if len(items) == 50 else None,
            }

        return errors.run_use_case(build)

    @bp.post("/api/projects/<project_id>/documents")
    def create(project_id: str) -> ResponseReturnValue:
        return errors.run_use_case(
            lambda: document_json(upload("evidence", project_id)), status=201
        )

    @bp.get("/api/projects/<project_id>/documents/<file_id>")
    def download(project_id: str, file_id: str) -> ResponseReturnValue:
        def build() -> Response:
            document, data = documents.get(project_id, file_id)
            response = send_file(
                BytesIO(data),
                mimetype=document.content_type,
                as_attachment=True,
                download_name=document.filename,
                max_age=0,
            )
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Cache-Control"] = "private, no-store"
            return response

        return errors.run_use_case(build)

    @bp.post("/api/projects/<project_id>/imports")
    def import_screenplay(project_id: str) -> ResponseReturnValue:
        request.max_content_length = 25 * 1024 * 1024 + 65536

        def build() -> dict[str, Any]:
            expected = request.form.get("expected_version", "")
            if not expected.isdecimal():
                raise InvalidDocument("expected_version is required")
            original = upload("original", project_id)
            _, data = documents.get(project_id, original.file_id)
            document, warnings = importer.parse(
                original.filename, data, original.storage_uri, original.file_id
            )
            draft = save_draft(
                drafts,
                content,
                original.organization_id,
                project_id,
                str(uuid4()),
                int(expected),
                document,
                actor(),
                datetime.now(UTC).isoformat(),
            )
            return {
                "draft": {
                    "project_id": project_id,
                    "version": draft.version,
                    "document": document,
                    "updated_at": draft.updated_at,
                    "updated_by": draft.updated_by,
                },
                "original": document_json(original),
                "warnings": warnings,
            }

        return errors.run_use_case(build, status=201)

    @bp.get("/api/projects/<project_id>/revisions/<revision_id>/exports/<format>")
    def export_screenplay(project_id: str, revision_id: str, format: str) -> ResponseReturnValue:
        def build() -> Response:
            if format not in {"pdf", "fdx"}:
                raise InvalidDocument("export format must be pdf or fdx")
            revision = drafts.revision(project_id, revision_id)
            document = read_document(
                content,
                Draft(
                    project_id,
                    revision.draft_version,
                    revision.content,
                    revision.created_by,
                    revision.created_at,
                ),
            )
            if document is None:
                raise InvalidDocument("revision has no screenplay")
            data = (
                screenplay_pdf(document, "Screenplay", revision.revision_id)
                if format == "pdf"
                else screenplay_fdx(document)
            )
            response = send_file(
                BytesIO(data),
                mimetype="application/pdf" if format == "pdf" else "application/xml",
                as_attachment=True,
                download_name=f"screenplay-{revision.revision_id}.{format}",
                max_age=0,
            )
            response.headers["Cache-Control"] = "private, no-store"
            return response

        return errors.run_use_case(build)

    return bp
