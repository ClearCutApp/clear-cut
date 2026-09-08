from typing import Any, Protocol

from clearcut.domain.document import ProjectDocument


class ProjectDocuments(Protocol):
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
    ) -> ProjectDocument: ...
    def metadata(self, project_id: str, file_id: str) -> ProjectDocument: ...
    def get(self, project_id: str, file_id: str) -> tuple[ProjectDocument, bytes]: ...
    def list(self, project_id: str, before: str | None = None) -> list[ProjectDocument]: ...


class ScreenplayImport(Protocol):
    def parse(
        self, filename: str, data: bytes, original_uri: str, file_id: str
    ) -> tuple[dict[str, Any], list[str]]: ...
