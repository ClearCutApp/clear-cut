"""Fenced delivery and explicit binding revocation, with bounded retries."""

from datetime import datetime, timedelta
from typing import Any

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from clearcut.domain.durable_analysis import LeaseLost
from clearcut.domain.notification import binding_fingerprint, valid_binding


class FirestoreNotificationDelivery:
    def __init__(self, client: Any) -> None:
        self.client = client

    def ready(self, at: datetime) -> list[str]:
        root = self.client.collection("notification_outbox")
        values: list[str] = []
        for state, field in (("pending", "available_at"), ("delivering", "lease_until")):
            query = (
                root.where(filter=FieldFilter("state", "==", state))
                .where(filter=FieldFilter(field, "<=", at))
                .order_by(field)
                .limit(10)
            )
            values.extend(row.id for row in query.stream())
        return values

    def claim(self, event_id: str, owner: str, at: datetime) -> dict[str, Any] | None:
        ref = self.client.collection("notification_outbox").document(event_id)

        @firestore.transactional
        def write(transaction: Any) -> dict[str, Any] | None:
            value = ref.get(transaction=transaction).to_dict() or {}
            state = value.get("state")
            if (
                state not in {"pending", "delivering"}
                or value.get("available_at" if state == "pending" else "lease_until", at) > at
            ):
                return None
            binding = (
                self.client.collection("notification_bindings")
                .document(value["binding_id"])
                .get(transaction=transaction)
                .to_dict()
                or {}
            )
            scope = (
                self.client.collection("project_access")
                .document(value["project_id"])
                .get(transaction=transaction)
                .to_dict()
                or {}
            )
            valid = (
                scope.get("organization_id") == value["organization_id"]
                and scope.get("notification_binding_id") == value["binding_id"]
                and valid_binding(binding, value["organization_id"], value["project_id"])
                and binding_fingerprint(binding) == value["binding_fingerprint"]
            )
            if not valid:
                transaction.update(ref, {"state": "blocked", "error_code": "destination_changed"})
                return None
            attempt = int(value.get("attempt", 0)) + 1
            if attempt > 5:
                transaction.update(ref, {"state": "failed", "error_code": "attempts_exhausted"})
                return None
            updates = {
                "state": "delivering",
                "owner": owner,
                "fence": int(value.get("fence", 0)) + 1,
                "attempt": attempt,
                "lease_until": at + timedelta(seconds=90),
            }
            transaction.update(ref, updates)
            return {**value, **updates, "binding": binding}

        result: dict[str, Any] | None = write(self.client.transaction())
        return result

    def finish(self, lease: dict[str, Any], at: datetime, state: str) -> None:
        if state not in {"delivered", "pending", "blocked"}:
            raise ValueError("invalid notification disposition")
        ref = self.client.collection("notification_outbox").document(lease["event_id"])

        @firestore.transactional
        def write(transaction: Any) -> None:
            current = ref.get(transaction=transaction).to_dict() or {}
            if (
                current.get("state") != "delivering"
                or current.get("owner") != lease["owner"]
                or current.get("fence") != lease["fence"]
                or current.get("lease_until", at) <= at
            ):
                raise LeaseLost("notification delivery lease lost")
            target = "failed" if state == "pending" and lease["attempt"] >= 5 else state
            transaction.update(
                ref,
                {
                    "state": target,
                    "updated_at": at,
                    "available_at": at
                    + timedelta(seconds=min(300, 15 * 2 ** (lease["attempt"] - 1))),
                    "error_code": None
                    if state == "delivered"
                    else "destination_changed"
                    if state == "blocked"
                    else "delivery_unconfirmed",
                },
            )

        write(self.client.transaction())
