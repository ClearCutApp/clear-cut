"""Private producer attention records; delivery never implies legal clearance."""

from datetime import datetime
from typing import Any, Protocol

from clearcut.domain.tracker import TrackerItem


class ProjectNotifications(Protocol):
    def record(self, item: TrackerItem, actor: str, reason: str, at: str) -> None: ...
    def list(
        self, project_id: str, actor: str, before: str | None = None
    ) -> list[dict[str, Any]]: ...
    def read(self, project_id: str, actor: str, notification_id: str, at: str) -> None: ...


class NotificationOutbox(Protocol):
    def ready(self, at: datetime) -> list[str]: ...
    def claim(self, event_id: str, owner: str, at: datetime) -> dict[str, Any] | None: ...
    def finish(self, lease: dict[str, Any], at: datetime, state: str) -> None: ...


class NotificationSender(Protocol):
    def send(self, lease: dict[str, Any]) -> None: ...
