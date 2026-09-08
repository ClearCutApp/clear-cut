"""Per-process demo draft storage; never selected by live composition."""

import hashlib
from threading import Lock

from clearcut.domain.errors import RecordNotFound
from clearcut.domain.screenplay import ContentReference, Draft, DraftConflict, Revision


class MemoryScreenplayContent:
    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    def put(
        self, organization_id: str, project_id: str, content_id: str, data: bytes
    ) -> ContentReference:
        uri = f"memory://{organization_id}/{project_id}/{content_id}"
        if uri in self._data:
            raise ValueError("content ID already exists")
        self._data[uri] = bytes(data)
        return ContentReference(uri, hashlib.sha256(data).hexdigest(), len(data))

    def get(self, reference: ContentReference) -> bytes:
        return self._data[reference.uri]


class MemoryDraftStore:
    def __init__(self) -> None:
        self._drafts: dict[str, Draft] = {}
        self._revisions: dict[tuple[str, str], Revision] = {}
        self._lock = Lock()

    def get_draft(self, project_id: str) -> Draft | None:
        return self._drafts.get(project_id)

    def save(
        self, project_id: str, expected_version: int, content: ContentReference, actor: str, at: str
    ) -> Draft:
        with self._lock:
            previous = self._drafts.get(project_id)
            version = previous.version if previous else 0
            if expected_version != version:
                raise DraftConflict(version)
            draft = Draft(project_id, version + 1, content, actor, at)
            self._drafts[project_id] = draft
            return draft

    def freeze(self, project_id: str, expected_version: int, actor: str, at: str) -> Revision:
        with self._lock:
            draft = self._drafts.get(project_id)
            if not draft or draft.content is None:
                raise RecordNotFound("save the draft before creating a revision")
            if draft.version != expected_version:
                raise DraftConflict(draft.version)
            revision_id = f"revision-{draft.version}"
            key = (project_id, revision_id)
            if key not in self._revisions:
                self._revisions[key] = Revision(
                    revision_id, project_id, draft.version, draft.content, actor, at
                )
            return self._revisions[key]

    def revision(self, project_id: str, revision_id: str) -> Revision:
        found = self._revisions.get((project_id, revision_id))
        if found is None:
            raise RecordNotFound("revision not found")
        return found

    def revisions(self, project_id: str, before_version: int | None = None) -> list[Revision]:
        found = [
            value
            for (project, _), value in self._revisions.items()
            if project == project_id
            and (before_version is None or value.draft_version < before_version)
        ]
        return sorted(found, key=lambda value: value.draft_version, reverse=True)[:50]
