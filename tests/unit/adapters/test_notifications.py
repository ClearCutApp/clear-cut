import hashlib
from copy import deepcopy
from datetime import timedelta
from typing import Any

import httpx
import pytest

from clearcut.adapters.gcp.notification_delivery import FirestoreNotificationDelivery
from clearcut.adapters.gcp.notifications import FirestoreNotifications
from clearcut.adapters.notify.delivery import deliver, endpoint_for
from clearcut.adapters.notify.webhook import WebhookNotifier
from clearcut.domain.durable_analysis import LeaseLost
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.identity import AccessDenied
from clearcut.domain.tracker import TrackerConflict
from clearcut.domain.workspace import InvalidWorkspace
from tests.unit.adapters.test_clearance_transactions import item, store
from tests.unit.adapters.test_durable_jobs import NOW

URL = "https://hooks.example.test/private"


def setup(bound: bool = True) -> tuple[Any, Any, FirestoreNotifications]:
    client, tracker = store()
    tracker.save([item()])
    if bound:
        client.data["project_access/project"]["notification_binding_id"] = "binding"
        client.data["notification_bindings/binding"] = {
            "enabled": True,
            "organization_id": "org",
            "project_ids": ["project"],
            "version": 1,
            "endpoint_env": "NOTIFY_WEBHOOK_URL",
            "endpoint_sha256": hashlib.sha256(URL.encode()).hexdigest(),
        }
    return client, tracker, FirestoreNotifications(client)


def queued() -> tuple[Any, Any, FirestoreNotifications, str]:
    client, tracker, notifications = setup()
    notifications.record(item(), "producer", "PRIVATE USER REASON", NOW.isoformat())
    key = next(key for key in client.data if key.startswith("notification_outbox/"))
    return client, tracker, notifications, key.split("/")[-1]


def test_unbound_private_project_records_in_app_without_global_fallback():
    client, _, notifications = setup(False)
    notifications.record(item(), "producer", "Please review", NOW.isoformat())
    records = [v for k, v in client.data.items() if "/notifications/" in k]
    assert len(records) == 1 and records[0]["delivery"] == "in_app_only"
    assert not any(k.startswith("notification_outbox/") for k in client.data)
    http = httpx.Client(transport=httpx.MockTransport(lambda request: pytest.fail("must not send")))
    with pytest.raises(SourceUnavailable):
        WebhookNotifier(http, URL, enabled=False).notify(item(), "secret")


@pytest.mark.parametrize("failure", ["foreign-org", "unassigned-project", "disabled"])
def test_org_binding_does_not_implicitly_authorize_private_project(failure):
    client, _, notifications = setup()
    binding = client.data["notification_bindings/binding"]
    if failure == "foreign-org":
        binding["organization_id"] = "other"
    if failure == "unassigned-project":
        binding["project_ids"] = ["other"]
    if failure == "disabled":
        binding["enabled"] = False
    notifications.record(item(), "producer", "review", NOW.isoformat())
    assert not any(k.startswith("notification_outbox/") for k in client.data)


def test_notification_authorization_version_and_limits_precede_all_writes():
    client, _, notifications = setup()
    before = deepcopy(client.data)
    with pytest.raises(AccessDenied):
        notifications.record(item(), "viewer", "review", NOW.isoformat())
    with pytest.raises(InvalidWorkspace):
        notifications.record(item(), "producer", "x" * 2001, NOW.isoformat())
    assert client.data == before
    client.data["project_access/project/clearances/asset"]["version"] = 2
    with pytest.raises(TrackerConflict):
        notifications.record(item(), "producer", "review", NOW.isoformat())
    assert not any(k.startswith("notification_outbox/") for k in client.data)


def test_dispatch_payload_excludes_content_and_redirects_are_not_followed():
    client, _, _, event_id = queued()
    intent = client.data["notification_outbox/" + event_id]
    assert "PRIVATE" not in str(intent) and "contact" not in intent
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(302, headers={"Location": "https://foreign.test"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(SourceUnavailable):
        deliver(http, URL, intent)
    assert len(seen) == 1 and b"PRIVATE" not in seen[0].content
    assert seen[0].headers["X-ClearCut-Event-ID"] == event_id
    assert seen[0].extensions["timeout"]["read"] == 20


@pytest.mark.parametrize("change", ["disabled", "version", "project", "endpoint"])
def test_queued_intent_never_reroutes_after_binding_change(change):
    client, _, _, event_id = queued()
    binding = client.data["notification_bindings/binding"]
    if change == "disabled":
        binding["enabled"] = False
    if change == "version":
        binding["version"] = 2
    if change == "project":
        client.data["project_access/project"]["notification_binding_id"] = "other"
    if change == "endpoint":
        binding["endpoint_sha256"] = "0" * 64
    delivery = FirestoreNotificationDelivery(client)
    assert delivery.claim(event_id, "worker", NOW) is None
    assert client.data["notification_outbox/" + event_id]["state"] == "blocked"


def test_unknown_response_retries_same_event_with_fenced_ack_and_bounded_attempts():
    client, _, _, event_id = queued()
    delivery = FirestoreNotificationDelivery(client)
    lease = delivery.claim(event_id, "one", NOW)
    assert lease and delivery.claim(event_id, "two", NOW) is None
    recovered = delivery.claim(event_id, "two", NOW + timedelta(seconds=91))
    assert recovered and recovered["event_id"] == lease["event_id"]
    with pytest.raises(LeaseLost):
        delivery.finish(lease, NOW + timedelta(seconds=92), "delivered")
    delivery.finish(recovered, NOW + timedelta(seconds=92), "pending")
    at = NOW + timedelta(seconds=500)
    for _ in range(3):
        lease = delivery.claim(event_id, "two", at)
        assert lease
        delivery.finish(lease, at, "pending")
        at += timedelta(seconds=500)
    assert client.data["notification_outbox/" + event_id]["state"] == "failed"


def test_changed_secret_value_and_non_https_destination_are_rejected():
    client, _, _ = setup()
    binding = client.data["notification_bindings/binding"]
    assert endpoint_for(binding, {"NOTIFY_WEBHOOK_URL": URL}) == URL
    with pytest.raises(ValueError):
        endpoint_for(binding, {"NOTIFY_WEBHOOK_URL": URL + "-new"})
    bad = "http://hooks.example.test"
    binding["endpoint_sha256"] = hashlib.sha256(bad.encode()).hexdigest()
    with pytest.raises(ValueError):
        endpoint_for(binding, {"NOTIFY_WEBHOOK_URL": bad})


def test_read_marks_are_private_and_revocation_prevents_new_marks():
    client, _, notifications, event_id = queued()
    notifications.read("project", "viewer", event_id, NOW.isoformat())
    assert "project_access/project/notifications/" + event_id + "/readers/viewer" in client.data
    before = deepcopy(client.data)
    client.data["project_access/project"]["grants"].pop("viewer")
    with pytest.raises(AccessDenied):
        notifications.read("project", "viewer", event_id, NOW.isoformat())
    assert len(client.data) == len(before)


def test_http_notifications_are_project_scoped_and_viewers_can_mark_their_own_read():
    from unittest.mock import Mock

    from flask import Flask

    from clearcut.adapters.http.identity import install_identity_boundary
    from clearcut.adapters.http.notifications import create_notifications_blueprint
    from tests.unit.adapters.test_identity_boundary import Access, Verifier

    app = Flask(__name__)
    notifications = Mock()
    notifications.list.return_value = []
    install_identity_boundary(app, Verifier(), Access())
    app.register_blueprint(create_notifications_blueprint(notifications))
    http = app.test_client()
    path = "/api/projects/one/notifications"
    assert http.get(path, headers={"Authorization": "Bearer bob"}).status_code == 404
    assert (
        http.post(path + "/notice/read", headers={"Authorization": "Bearer bob"}).status_code == 404
    )
    notifications.list.assert_not_called()
    notifications.read.assert_not_called()
    assert http.get(path, headers={"Authorization": "Bearer viewer"}).status_code == 200
    result = http.post(path + "/notice/read", headers={"Authorization": "Bearer viewer"})
    assert result.status_code == 200 and result.headers["Cache-Control"] == "no-store"
    assert notifications.read.call_args.args[:3] == ("one", "viewer", "notice")


def test_binding_provisioning_is_atomic_idempotent_and_requires_versioned_changes():
    from infra.provision_notification_binding import apply

    client, _, _ = setup()
    binding = deepcopy(client.data["notification_bindings/binding"])
    before = deepcopy(client.data)
    apply(client, "binding", binding)
    assert client.data == before
    changed = {**binding, "enabled": False}
    with pytest.raises(ValueError):
        apply(client, "binding", changed)
    assert client.data == before
    changed["version"] = 2
    apply(client, "binding", changed)
    assert client.data["notification_bindings/binding"]["enabled"] is False
    before = deepcopy(client.data)
    foreign = {**changed, "project_ids": ["project", "foreign"], "version": 3}
    with pytest.raises(ValueError):
        apply(client, "binding", foreign)
    assert client.data == before


def test_dispatcher_records_failure_without_acknowledging_and_does_not_retry_inline():
    from unittest.mock import Mock

    from clearcut.application.dispatch_notifications import DispatchNotifications

    outbox, sender = Mock(), Mock()
    outbox.ready.return_value = ["event"]
    lease = {"event_id": "event"}
    outbox.claim.return_value = lease
    sender.send.side_effect = SourceUnavailable("unconfirmed")
    assert DispatchNotifications(outbox, sender, lambda: NOW).dispatch("worker") == 0
    sender.send.assert_called_once_with(lease)
    outbox.finish.assert_called_once_with(lease, NOW, "pending")
