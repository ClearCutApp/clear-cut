"""Explicit demo project documents; no credentials or live persistence."""

from hashlib import sha256
from uuid import uuid4

from clearcut.domain.document import ProjectDocument
from clearcut.domain.errors import RecordNotFound


class MemoryProjectDocuments:
    def __init__(self) -> None:
        self._documents: dict[tuple[str, str], tuple[ProjectDocument, bytes]] = {}

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
        file_id = str(uuid4())
        document = ProjectDocument(
            file_id,
            organization_id,
            project_id,
            filename,
            content_type,
            len(data),
            sha256(data).hexdigest(),
            "memory://" + file_id,
            kind,
            actor,
            at,
            revision_id,
        )
        self._documents[(project_id, file_id)] = (document, bytes(data))
        return document

    def metadata(self, project_id: str, file_id: str) -> ProjectDocument:
        return self.get(project_id, file_id)[0]

    def get(self, project_id: str, file_id: str) -> tuple[ProjectDocument, bytes]:
        found = self._documents.get((project_id, file_id))
        if not found:
            raise RecordNotFound("document not found")
        return found

    def list(self, project_id: str, before: str | None = None) -> list[ProjectDocument]:
        documents = sorted(
            [item[0] for (project, _), item in self._documents.items() if project == project_id],
            key=lambda item: (item.created_at, item.file_id),
            reverse=True,
        )
        if before:
            index = next(
                (i for i, document in enumerate(documents) if document.file_id == before), None
            )
            if index is None:
                raise RecordNotFound("cursor not found")
            documents = documents[index + 1 :]
        return documents[:50]
