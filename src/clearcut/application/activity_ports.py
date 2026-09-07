"""Operational outbox ownership and deduplicated ClickHouse activity."""

from __future__ import annotations

import builtins
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from clearcut.domain.activity import ActivityEvent


@dataclass(frozen=True)
class OutboxLease:
    event: ActivityEvent
    owner: str
    fence: int
    attempt: int


class ActivityOutbox(Protocol):
    def ready(self, at: datetime, limit: int = 50) -> list[str]: ...
    def claim(self, event_id: str, owner: str, at: datetime) -> OutboxLease | None: ...
    def acknowledge(self, lease: OutboxLease, at: datetime) -> None: ...
    def fail(self, lease: OutboxLease, at: datetime) -> None: ...


class ActivityStore(Protocol):
    def append(self, event: ActivityEvent) -> None: ...
    def list(
        self, organization_id: str, project_id: str, before: tuple[str, str] | None = None
    ) -> list[ActivityEvent]: ...
    def trends(self, organization_id: str, project_id: str) -> builtins.list[ActivityEvent]: ...
