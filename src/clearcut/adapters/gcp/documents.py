"""Immutable GCS originals and Firestore document metadata in a private project."""

import hashlib
from dataclasses import asdict
from pathlib import PurePosixPath
from typing import Any
from uuid import uuid4

from clearcut.domain.activity import activity_envelope
from clearcut.domain.document import InvalidDocument, ProjectDocument
from clearcut.domain.errors import RecordNotFound, SourceUnavailable


class GcpProjectDocuments:
    def __init__(self, firestore_client: Any, storage_client: Any, bucket: str) -> None:
        self._db = firestore_client
        self._storage = storage_client
        self._bucket = bucket

    def _collection(self, project_id: str) -> Any:
        if not project_id or "/" in project_id or "\\" in project_id:
            raise RecordNotFound("project not found")
        return self._db.collection("project_access").document(project_id).collection("documents")

    def put(
        self,
        organization_id: str,
        project_id: str,
        filename: str,
        content_type: str,
        data: bytes,
        kind: str,
        actor: str,
        at: str,
        revision_id: str = "",
    ) -> ProjectDocument:
        if not organization_id or "/" in organization_id or "\\" in organization_id:
            raise InvalidDocument("invalid organization")
        filename = PurePosixPath(filename.replace("\\", "/")).name[:200]
        if not filename or filename in {".", ".."} or any(ord(char) < 32 for char in filename):
            raise InvalidDocument("a valid filename is required")
        collection = self._collection(project_id)
        file_id = str(uuid4())
        key = f"organizations/{organization_id}/projects/{project_id}/files/{file_id}/{filename}"
        document = ProjectDocument(
            file_id,
            organization_id,
            project_id,
            filename,
            content_type,
            len(data),
            hashlib.sha256(data).hexdigest(),
            f"gs://{self._bucket}/{key}",
            kind,
            actor,
            at,
            revision_id,
        )
        try:
            self._storage.bucket(self._bucket).blob(key).upload_from_string(
                data, content_type=content_type, if_generation_match=0
            )
            batch = self._db.batch()
            batch.create(collection.document(file_id), asdict(document))
            batch.create(
                self._db.collection("outbox").document("document-" + file_id),
                activity_envelope(
                    "document-" + file_id,
                    organization_id,
                    project_id,
                    "document_created",
                    at,
                    1,
                    {"file_id": file_id, "document_kind": kind, "size_bytes": len(data)},
                ),
            )
            batch.commit()
        except Exception as exc:
            raise SourceUnavailable("document storage unavailable") from exc
        return document

    def metadata(self, project_id: str, file_id: str) -> ProjectDocument:
        if not file_id or "/" in file_id or "\\" in file_id:
            raise RecordNotFound("document not found")
        try:
            data = self._collection(project_id).document(file_id).get().to_dict()
            if not data:
                raise RecordNotFound("document not found")
            document = ProjectDocument(**data)
            prefix = f"gs://{self._bucket}/organizations/{document.organization_id}/projects/{project_id}/files/{file_id}/"
            if document.project_id != project_id or not document.storage_uri.startswith(prefix):
                raise RecordNotFound("document not found")
            return document
        except RecordNotFound:
            raise
        except Exception as exc:
            raise SourceUnavailable("document lookup unavailable") from exc

    def get(self, project_id: str, file_id: str) -> tuple[ProjectDocument, bytes]:
        document = self.metadata(project_id, file_id)
        try:
            content = (
                self._storage.bucket(self._bucket)
                .blob(document.storage_uri.removeprefix(f"gs://{self._bucket}/"))
                .download_as_bytes(start=0, end=25 * 1024 * 1024)
            )
            if (
                len(content) != document.size_bytes
                or hashlib.sha256(content).hexdigest() != document.sha256
            ):
                raise SourceUnavailable("document integrity check failed")
            return document, content
        except SourceUnavailable:
            raise
        except Exception as exc:
            raise SourceUnavailable("document download unavailable") from exc

    def list(self, project_id: str, before: str | None = None) -> list[ProjectDocument]:
        try:
            query = self._collection(project_id).order_by("created_at", direction="DESCENDING")
            if before:
                if "/" in before or "\\" in before:
                    raise RecordNotFound("cursor not found")
                snapshot = self._collection(project_id).document(before).get()
                if not snapshot.exists:
                    raise RecordNotFound("cursor not found")
                query = query.start_after(snapshot)
            return [ProjectDocument(**row.to_dict()) for row in query.limit(50).stream()]
        except RecordNotFound:
            raise
        except Exception as exc:
            raise SourceUnavailable("document list unavailable") from exc
