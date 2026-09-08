"""Firestore transactions publish immutable content references, never large JSON."""

from dataclasses import asdict
from typing import Any

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from clearcut.domain.activity import activity_envelope
from clearcut.domain.errors import RecordNotFound, SourceUnavailable
from clearcut.domain.identity import AccessDenied, project_permits
from clearcut.domain.screenplay import ContentReference, Draft, DraftConflict, Revision


def _draft(data: dict[str, Any]) -> Draft:
    return Draft(
        project_id=data["project_id"],
        version=int(data["version"]),
        content=ContentReference(**data["content"]) if data.get("content") else None,
        updated_by=data["updated_by"],
        updated_at=data["updated_at"],
    )


def _revision(data: dict[str, Any]) -> Revision:
    return Revision(
        revision_id=data["revision_id"],
        project_id=data["project_id"],
        draft_version=int(data["draft_version"]),
        content=ContentReference(**data["content"]),
        created_by=data["created_by"],
        created_at=data["created_at"],
    )


class FirestoreDraftStore:
    def __init__(self, client: Any) -> None:
        self._client = client

    def _project(self, project_id: str) -> Any:
        return self._client.collection("project_access").document(project_id)

    def _authorize(self, project_id: str, actor: str, transaction: Any) -> dict[str, Any]:
        scope = self._project(project_id).get(transaction=transaction).to_dict() or {}
        member = (
            self._client.collection("organizations")
            .document(scope.get("organization_id", "_"))
            .collection("members")
            .document(actor)
            .get(transaction=transaction)
            .to_dict()
            or {}
        )
        if not project_permits(scope, member, actor, "script"):
            raise AccessDenied("project editing permission changed")
        return scope

    def get_draft(self, project_id: str) -> Draft | None:
        try:
            data = (
                self._project(project_id).collection("drafts").document("current").get().to_dict()
            )
            return _draft(data) if data else None
        except Exception as exc:
            raise SourceUnavailable("draft lookup unavailable") from exc

    def save(
        self, project_id: str, expected_version: int, content: ContentReference, actor: str, at: str
    ) -> Draft:
        ref = self._project(project_id).collection("drafts").document("current")

        @firestore.transactional
        def write(transaction: Any) -> Draft:
            self._authorize(project_id, actor, transaction)
            previous = ref.get(transaction=transaction).to_dict() or {}
            version = int(previous.get("version", 0))
            if version != expected_version:
                raise DraftConflict(version)
            draft = Draft(project_id, version + 1, content, actor, at)
            transaction.set(ref, asdict(draft))
            return draft

        try:
            result: Draft = write(self._client.transaction())
            return result
        except (DraftConflict, AccessDenied):
            raise
        except Exception as exc:
            raise SourceUnavailable("draft save unavailable") from exc

    def freeze(self, project_id: str, expected_version: int, actor: str, at: str) -> Revision:
        project = self._project(project_id)
        revision_id = f"revision-{expected_version}"
        revision_ref = project.collection("revisions").document(revision_id)

        @firestore.transactional
        def write(transaction: Any) -> Revision:
            scope = self._authorize(project_id, actor, transaction)
            data = (
                project.collection("drafts")
                .document("current")
                .get(transaction=transaction)
                .to_dict()
            )
            existing = revision_ref.get(transaction=transaction).to_dict()
            if not data:
                raise RecordNotFound("save the draft before creating a revision")
            draft = _draft(data)
            if draft.version != expected_version:
                raise DraftConflict(draft.version)
            if existing:
                return _revision(existing)
            if draft.content is None:
                raise RecordNotFound("draft has no content")
            revision = Revision(revision_id, project_id, draft.version, draft.content, actor, at)
            transaction.create(revision_ref, asdict(revision))
            outbox = self._client.collection("outbox").document(
                f"revision-{project_id}-{draft.version}"
            )
            transaction.create(
                outbox,
                activity_envelope(
                    f"revision-{project_id}-{draft.version}",
                    str(scope.get("organization_id", "")),
                    project_id,
                    "revision_saved",
                    at,
                    draft.version,
                    {"revision_id": revision_id},
                ),
            )
            return revision

        try:
            result: Revision = write(self._client.transaction())
            return result
        except (DraftConflict, RecordNotFound, AccessDenied):
            raise
        except Exception as exc:
            raise SourceUnavailable("revision save unavailable") from exc

    def revision(self, project_id: str, revision_id: str) -> Revision:
        if not revision_id or "/" in revision_id or "\\" in revision_id:
            raise RecordNotFound("revision not found")
        try:
            data = (
                self._project(project_id)
                .collection("revisions")
                .document(revision_id)
                .get()
                .to_dict()
            )
        except Exception as exc:
            raise SourceUnavailable("revision lookup unavailable") from exc
        if not data:
            raise RecordNotFound("revision not found")
        return _revision(data)

    def revisions(self, project_id: str, before_version: int | None = None) -> list[Revision]:
        try:
            query = self._project(project_id).collection("revisions")
            if before_version is not None:
                query = query.where(filter=FieldFilter("draft_version", "<", before_version))
            query = query.order_by("draft_version", direction=firestore.Query.DESCENDING).limit(50)
            return [_revision(row.to_dict()) for row in query.stream()]
        except Exception as exc:
            raise SourceUnavailable("revision history unavailable") from exc
