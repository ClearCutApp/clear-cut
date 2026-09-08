"""Private, dated research for saved production locations."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from clearcut.application.ports import GroundedAnswer


@dataclass(frozen=True)
class LocalResearchSnapshot:
    epoch: int
    settings_version: int
    production_context_json: str
    records: list[dict[str, Any]]
    history_window: int = 50


class LocalResearchStore(Protocol):
    def capture(self, project_id: str) -> LocalResearchSnapshot: ...

    def list(self, project_id: str) -> list[dict[str, Any]]: ...

    def save(
        self,
        project_id: str,
        actor: str,
        research_id: str,
        expected_settings_version: int,
        location_index: int,
        question: str,
        answer: GroundedAnswer,
        at: datetime,
    ) -> dict[str, Any]: ...
