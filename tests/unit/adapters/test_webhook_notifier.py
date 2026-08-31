"""Tests for the outbound webhook Notifier adapter (CP-024, docs/plan/sdd.md
Section 3).

The transport is faked at the httpx level (`httpx.MockTransport`), the same
seam CP-010 established, rather than patching `httpx.Client` (AGENT.md
Section 5). Notifications here are internal alerts to the production team,
never outbound legal mail (docs/plan/agentic-workflow.md Section 5/7).
"""

from __future__ import annotations

import json

import httpx
import pytest

from clearcut.adapters.notify.webhook import NotificationFailed, WebhookNotifier
from clearcut.application.ports import Notifier
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.tracker import TrackerItem, TrackerState

_WEBHOOK_URL = "https://example.com/hooks/notify"

_ITEM = TrackerItem(
    item_id="TRK-001",
    project_id="proj-1",
    finding_id="EVT-001",
    scene_numbers=(3,),
    state=TrackerState.BLOCKED,
    required_document="Sync License",
    contact="rights@example.com",
    litigation_posture="none on record",
    note="",
    updated_at="2026-08-30T00:00:00Z",
    version=1,
)


def _adapter(*, status: int = 202, captured: list[httpx.Request] | None = None) -> WebhookNotifier:
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        return httpx.Response(status)

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    return WebhookNotifier(http_client, _WEBHOOK_URL)


def test_adapter_implements_notifier_port() -> None:
    adapter = _adapter()
    checked: Notifier = adapter
    assert isinstance(checked, Notifier)


def test_notify_posts_json_body_with_the_five_fields() -> None:
    captured: list[httpx.Request] = []
    adapter = _adapter(captured=captured)

    adapter.notify(_ITEM, "scene 3 rewrite dropped the licensed cue")

    assert len(captured) == 1
    assert captured[0].url == _WEBHOOK_URL
    assert captured[0].method == "POST"
    body = json.loads(captured[0].content)
    assert body["item_id"] == "TRK-001"
    assert body["finding_id"] == "EVT-001"
    assert body["state"] == "BLOCKED"
    assert body["needs_review"] is False
    assert body["reason"] == "scene 3 rewrite dropped the licensed cue"


def test_non_2xx_response_raises_notification_failed_with_status_code() -> None:
    adapter = _adapter(status=500)

    with pytest.raises(NotificationFailed) as excinfo:
        adapter.notify(_ITEM, "reason")

    assert excinfo.value.status_code == 500
    assert "500" in str(excinfo.value)


def test_connect_error_raises_notification_failed_with_a_connection_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = WebhookNotifier(http_client, _WEBHOOK_URL)

    with pytest.raises(NotificationFailed) as excinfo:
        adapter.notify(_ITEM, "reason")

    assert type(excinfo.value) is NotificationFailed
    assert "connection refused" in str(excinfo.value)
    assert "responded with status" not in str(excinfo.value)
    assert excinfo.value.status_code is None


def test_connect_error_message_differs_from_non_2xx_status_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    connect_client = httpx.Client(transport=httpx.MockTransport(handler))
    connect_adapter = WebhookNotifier(connect_client, _WEBHOOK_URL)
    status_adapter = _adapter(status=500)

    with pytest.raises(NotificationFailed) as connect_excinfo:
        connect_adapter.notify(_ITEM, "reason")
    with pytest.raises(NotificationFailed) as status_excinfo:
        status_adapter.notify(_ITEM, "reason")

    assert str(connect_excinfo.value) != str(status_excinfo.value)


def test_read_timeout_is_catchable_as_source_unavailable_alone() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = WebhookNotifier(http_client, _WEBHOOK_URL)

    with pytest.raises(SourceUnavailable):
        adapter.notify(_ITEM, "reason")


def test_blank_webhook_url_is_refused_in_constructor() -> None:
    http_client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(202)))

    with pytest.raises(ValueError):
        WebhookNotifier(http_client, "   ")
