"""Atomic human clearance writes and immutable audit reads."""

from typing import Any, Protocol

from clearcut.domain.tracker import TrackerItem


class TrackerMutations(Protocol):
    def compare_save(self, item: TrackerItem, expected_version: int, actor: str) -> None: ...

    def history(
        self, project_id: str, item_id: str, before_version: int | None = None
    ) -> list[dict[str, Any]]: ...


class ClearanceConfirmation(Protocol):
    def compare_reconfirm(
        self,
        item: TrackerItem,
        expected_version: int,
        actor: str,
        generation_id: str,
        revision_id: str,
        production_context_json: str = "{}",
    ) -> None: ...
