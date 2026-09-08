"""Deliver authorized intents with bounded retry and no false success receipt."""

from collections.abc import Callable
from datetime import datetime

from clearcut.application.notification_ports import NotificationOutbox, NotificationSender
from clearcut.domain.errors import SourceUnavailable


class DispatchNotifications:
    def __init__(
        self, outbox: NotificationOutbox, sender: NotificationSender, clock: Callable[[], datetime]
    ) -> None:
        self.outbox, self.sender, self.clock = outbox, sender, clock

    def dispatch(self, owner: str) -> int:
        acknowledged = 0
        for event_id in self.outbox.ready(self.clock()):
            lease = self.outbox.claim(event_id, owner, self.clock())
            if lease is None:
                continue
            try:
                self.sender.send(lease)
            except ValueError:
                self.outbox.finish(lease, self.clock(), "blocked")
            except SourceUnavailable:
                self.outbox.finish(lease, self.clock(), "pending")
            else:
                self.outbox.finish(lease, self.clock(), "delivered")
                acknowledged += 1
        return acknowledged
