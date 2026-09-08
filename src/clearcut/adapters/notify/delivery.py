"""Bounded webhook transport: immutable destination and content-free event payload."""

import hashlib
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

import httpx

from clearcut.domain.errors import SourceUnavailable


def endpoint_for(binding: dict[str, Any], environment: Mapping[str, str]) -> str:
    endpoint = environment.get(binding.get("endpoint_env", ""), "")
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or hashlib.sha256(endpoint.encode()).hexdigest() != binding.get("endpoint_sha256")
    ):
        raise ValueError("notification destination is unavailable or changed")
    return endpoint


def deliver(client: httpx.Client, endpoint: str, intent: dict[str, Any]) -> None:
    payload = {
        field: intent[field]
        for field in ("event_id", "organization_id", "project_id", "item_id", "reason_code")
    }
    try:
        response = client.post(
            endpoint,
            json=payload,
            headers={"X-ClearCut-Event-ID": intent["event_id"]},
            timeout=20,
            follow_redirects=False,
        )
    except httpx.HTTPError:
        raise SourceUnavailable("notification delivery unavailable") from None
    if not 200 <= response.status_code < 300:
        raise SourceUnavailable("notification destination did not accept the event")


class BoundNotificationSender:
    def __init__(self, environment: Mapping[str, str]) -> None:
        self.environment = environment

    def send(self, lease: dict[str, Any]) -> None:
        endpoint = endpoint_for(lease["binding"], self.environment)
        with httpx.Client() as client:
            deliver(client, endpoint, lease)
