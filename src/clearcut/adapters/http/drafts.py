"""Private screenplay drafts and immutable revision history."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from flask import Blueprint, g, request
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import drafts_spec, errors, validators
from clearcut.application.draft_ports import DraftStore, ScreenplayContent
from clearcut.application.screenplay_drafts import read_document, save_draft
from clearcut.domain.screenplay import MAX_DOCUMENT_BYTES, Draft, InvalidScreenplay, Revision

PATHS = drafts_spec.PATHS
SCHEMAS = drafts_spec.SCHEMAS
TAG = "Screenplay editor"
TAG_DESCRIPTION = "Expected-version drafts and immutable saved revisions."


def _version(payload: dict[str, Any]) -> int:
    value = payload.get("expected_version")
    if type(value) is not int or value < 0:
        raise InvalidScreenplay("expected_version must be a nonnegative integer")
    return value


def _revision_json(revision: Revision) -> dict[str, Any]:
    return {
        "revision_id": revision.revision_id,
        "project_id": revision.project_id,
        "draft_version": revision.draft_version,
        "sha256": revision.content.sha256,
        "created_at": revision.created_at,
        "created_by": revision.created_by,
    }


def create_drafts_blueprint(store: DraftStore, content: ScreenplayContent) -> Blueprint:
    bp = Blueprint("clearcut_drafts", __name__)

    @bp.errorhandler(413)
    def oversized(error: Any) -> ResponseReturnValue:
        return errors.error_response(413, "screenplay request exceeds 8 MiB")

    def draft_json(draft: Draft) -> dict[str, Any]:
        return {
            "project_id": draft.project_id,
            "version": draft.version,
            "document": read_document(content, draft),
            "updated_at": draft.updated_at,
            "updated_by": draft.updated_by,
        }

    def actor() -> str:
        identity = getattr(g, "identity", None)
        return identity.user_id if identity else "demo"

    @bp.get("/api/projects/<project_id>/draft")
    def show(project_id: str) -> ResponseReturnValue:
        return errors.run_use_case(
            lambda: draft_json(store.get_draft(project_id) or Draft(project_id, 0, None, "", ""))
        )

    @bp.put("/api/projects/<project_id>/draft")
    def save(project_id: str) -> ResponseReturnValue:
        request.max_content_length = MAX_DOCUMENT_BYTES + 65536
        payload = validators.json_body()

        def build() -> dict[str, Any]:
            document = payload.get("document")
            if not isinstance(document, dict):
                raise InvalidScreenplay("document is required")
            draft = save_draft(
                store,
                content,
                getattr(g, "organization_id", "demo"),
                project_id,
                str(uuid4()),
                _version(payload),
                document,
                actor(),
                datetime.now(UTC).isoformat(),
            )
            return draft_json(draft)

        return errors.run_use_case(build)

    @bp.post("/api/projects/<project_id>/revisions")
    def freeze(project_id: str) -> ResponseReturnValue:
        payload = validators.json_body()
        return errors.run_use_case(
            lambda: _revision_json(
                store.freeze(project_id, _version(payload), actor(), datetime.now(UTC).isoformat())
            ),
            status=201,
        )

    @bp.get("/api/projects/<project_id>/revisions")
    def history(project_id: str) -> ResponseReturnValue:
        def build() -> dict[str, Any]:
            before = request.args.get("before_version")
            if before is not None and (not before.isdecimal() or int(before) < 1):
                raise InvalidScreenplay("before_version must be a positive integer")
            revisions = store.revisions(project_id, int(before) if before else None)
            return {
                "revisions": [_revision_json(item) for item in revisions],
                "next_before_version": revisions[-1].draft_version
                if len(revisions) == 50
                else None,
            }

        return errors.run_use_case(build)

    @bp.get("/api/projects/<project_id>/revisions/<revision_id>")
    def revision_show(project_id: str, revision_id: str) -> ResponseReturnValue:
        def build() -> dict[str, Any]:
            revision = store.revision(project_id, revision_id)
            return {
                **_revision_json(revision),
                "document": read_document(
                    content,
                    Draft(
                        project_id,
                        revision.draft_version,
                        revision.content,
                        revision.created_by,
                        revision.created_at,
                    ),
                ),
            }

        return errors.run_use_case(build)

    return bp
