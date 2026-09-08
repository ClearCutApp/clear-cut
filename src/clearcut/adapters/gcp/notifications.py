"""Private notifications and explicit project-bound webhook launch intents."""

import uuid
from datetime import datetime
from typing import Any

from google.cloud import firestore

from clearcut.domain.errors import RecordNotFound
from clearcut.domain.identity import AccessDenied, project_permits
from clearcut.domain.notification import binding_fingerprint, valid_binding
from clearcut.domain.tracker import TrackerConflict, TrackerItem
from clearcut.domain.workspace import InvalidWorkspace


class FirestoreNotifications:
    def __init__(self, client: Any) -> None:
        self.client = client

    def _authorize(
        self, transaction: Any, project_id: str, actor: str, action: str
    ) -> tuple[Any, dict[str, Any]]:
        ref = self.client.collection("project_access").document(project_id)
        scope = ref.get(transaction=transaction).to_dict() or {}
        member = (
            self.client.collection("organizations")
            .document(scope.get("organization_id", "_"))
            .collection("members")
            .document(actor)
            .get(transaction=transaction)
            .to_dict()
            or {}
        )
        if not project_permits(scope, member, actor, action):
            raise AccessDenied("project notification access required")
        return ref, scope

    def record(self, item: TrackerItem, actor: str, reason: str, at: str) -> None:
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000:
            raise InvalidWorkspace("notification reason must contain 1–2000 characters")
        event_id = uuid.uuid4().hex
        timestamp = datetime.fromisoformat(at.replace("Z", "+00:00"))

        @firestore.transactional
        def write(transaction: Any) -> None:
            ref, scope = self._authorize(transaction, item.project_id, actor, "produce")
            generation = scope.get("active_generation")
            root = (
                ref.collection("clearance_generations").document(generation) if generation else ref
            )
            base = (
                root.collection("items" if generation else "clearances")
                .document(item.item_id)
                .get(transaction=transaction)
                .to_dict()
                or {}
            )
            override = (
                root.collection("overrides")
                .document(item.item_id)
                .get(transaction=transaction)
                .to_dict()
                if generation
                else None
            )
            current = override or base
            if not current:
                raise RecordNotFound("clearance not found")
            if current.get("version") != item.version:
                raise TrackerConflict(int(current.get("version", 0)))
            binding_id = scope.get("notification_binding_id", "")
            binding = (
                self.client.collection("notification_bindings")
                .document(binding_id)
                .get(transaction=transaction)
                .to_dict()
                or {}
                if binding_id
                else {}
            )
            delivery = valid_binding(binding, scope["organization_id"], item.project_id)
            transaction.create(
                ref.collection("notifications").document(event_id),
                {
                    "notification_id": event_id,
                    "project_id": item.project_id,
                    "organization_id": scope["organization_id"],
                    "item_id": item.item_id,
                    "item_version": item.version,
                    "actor": actor,
                    "reason": reason.strip(),
                    "created_at": timestamp,
                    "delivery": "queued" if delivery else "in_app_only",
                },
            )
            if delivery:
                transaction.create(
                    self.client.collection("notification_outbox").document(event_id),
                    {
                        "event_id": event_id,
                        "organization_id": scope["organization_id"],
                        "project_id": item.project_id,
                        "item_id": item.item_id,
                        "reason_code": "manual_attention",
                        "binding_id": binding_id,
                        "binding_fingerprint": binding_fingerprint(binding),
                        "state": "pending",
                        "attempt": 0,
                        "fence": 0,
                        "available_at": timestamp,
                    },
                )

        write(self.client.transaction())

    def list(self, project_id: str, actor: str, before: str | None = None) -> list[dict[str, Any]]:
        # HTTP reauthorizes every request; per-user read marks never grant access.
        ref = self.client.collection("project_access").document(project_id)
        records = ref.collection("notifications")
        query = records.order_by("created_at", direction="DESCENDING").order_by(
            "__name__", direction="DESCENDING"
        )
        if before:
            cursor = records.document(before).get()
            if not cursor.to_dict():
                raise RecordNotFound("notification cursor not found")
            query = query.start_after(cursor)
        values = []
        for snapshot in query.limit(50).stream():
            value = snapshot.to_dict()
            value["read"] = bool(
                records.document(value["notification_id"])
                .collection("readers")
                .document(actor)
                .get()
                .to_dict()
            )
            intent = (
                self.client.collection("notification_outbox")
                .document(value["notification_id"])
                .get()
                .to_dict()
            )
            if intent:
                value["delivery"] = intent["state"]
            value["created_at"] = value["created_at"].isoformat()
            values.append(value)
        return values

    def read(self, project_id: str, actor: str, notification_id: str, at: str) -> None:
        @firestore.transactional
        def write(transaction: Any) -> None:
            ref, _ = self._authorize(transaction, project_id, actor, "read")
            record = ref.collection("notifications").document(notification_id)
            if not record.get(transaction=transaction).to_dict():
                raise RecordNotFound("notification not found")
            transaction.set(record.collection("readers").document(actor), {"read_at": at})

        write(self.client.transaction())
