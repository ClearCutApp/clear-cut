"""Notifies a producer over an outbound webhook (docs/plan/sdd.md Section 3).

`Notifier` covers one internal alert to the production team, never outbound
legal correspondence -- the human-in-the-loop rule at
docs/plan/agentic-workflow.md Section 5/7 covers legal mail only, so a
regression notice on a delta may fire automatically through this adapter.
"""

from __future__ import annotations

import httpx

from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.tracker import TrackerItem


class NotificationFailed(SourceUnavailable):
    """Raised when the webhook could not be reached, timed out, or responded
    with a non-2xx status."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class WebhookNotifier:
    """Implements `Notifier` over an outbound HTTP webhook."""

    def __init__(self, http_client: httpx.Client, webhook_url: str) -> None:
        if not webhook_url.strip():
            raise ValueError("webhook_url must not be blank")
        self._client = http_client
        self._url = webhook_url

    def notify(self, item: TrackerItem, reason: str) -> None:
        try:
            response = self._client.post(self._url, json=_body(item, reason))
        except httpx.TransportError as error:
            raise NotificationFailed(f"webhook request failed: {error}") from error
        if not response.is_success:
            raise NotificationFailed(
                f"webhook responded with status {response.status_code}",
                status_code=response.status_code,
            )


def _body(item: TrackerItem, reason: str) -> dict[str, str | bool]:
    return {
        "item_id": item.item_id,
        "finding_id": item.finding_id,
        "state": item.state.value,
        "needs_review": item.needs_review,
        "reason": reason,
    }
