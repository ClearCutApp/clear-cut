"""Post-commit scene indexing, with explicit revision freshness."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from clearcut.domain.screenplay import ContentReference


@dataclass(frozen=True)
class LoreLease:
    analysis_id: str
    organization_id: str
    project_id: str
    revision_id: str
    manifest: ContentReference
    provider_config_json: str
    owner: str
    fence: int
    cursor: int
    checkpoint: ContentReference | None


class LoreProjectionQueue(Protocol):
    def ready(self, at: datetime, limit: int = 10) -> list[str]: ...
    def claim(self, analysis_id: str, owner: str, at: datetime) -> LoreLease | None: ...
    def heartbeat(self, lease: LoreLease, at: datetime) -> None: ...
    def checkpoint(self, lease: LoreLease, content: ContentReference, at: datetime) -> None: ...
    def advance(self, lease: LoreLease, cursor: int, complete: bool, at: datetime) -> None: ...
    def fail(self, lease: LoreLease, at: datetime) -> None: ...
    def current(self, project_id: str) -> dict[str, Any]: ...


class SceneVectors(Protocol):
    def embed(self, texts: list[str], provider_config_json: str) -> list[list[float]]: ...
    def append(
        self, lease: LoreLease, scenes: list[dict[str, Any]], embeddings: list[list[float]]
    ) -> None: ...
    def search(self, scope: dict[str, Any], question: str, limit: int) -> list[dict[str, Any]]: ...
