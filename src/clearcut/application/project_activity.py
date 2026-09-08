"""Bounded delivery with immutable retries after an accepted-but-unacked insert."""

from collections.abc import Callable
from datetime import datetime

from clearcut.application.activity_ports import ActivityOutbox, ActivityStore
from clearcut.domain.errors import SourceUnavailable


class ProjectActivity:
    def __init__(
        self, outbox: ActivityOutbox, activity: ActivityStore, clock: Callable[[], datetime]
    ) -> None:
        self.outbox, self.activity, self.clock = outbox, activity, clock

    def dispatch(self, owner: str) -> int:
        acknowledged = 0
        for event_id in self.outbox.ready(self.clock()):
            lease = self.outbox.claim(event_id, owner, self.clock())
            if lease is None:
                continue
            try:
                self.activity.append(lease.event)
            except SourceUnavailable:
                self.outbox.fail(lease, self.clock())
                continue
            self.outbox.acknowledge(lease, self.clock())
            acknowledged += 1
        return acknowledged
