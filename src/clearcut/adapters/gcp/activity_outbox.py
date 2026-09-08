"""Fenced Firestore outbox leases; acknowledgements never precede ClickHouse."""

from datetime import datetime, timedelta
from typing import Any

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from clearcut.application.activity_ports import OutboxLease
from clearcut.domain.activity import read_event
from clearcut.domain.durable_analysis import LeaseLost
from clearcut.domain.errors import SourceUnavailable


class FirestoreActivityOutbox:
    def __init__(self, client: Any) -> None:
        self.client = client

    def ready(self, at: datetime, limit: int = 50) -> list[str]:
        root = self.client.collection("outbox")
        try:
            # Each state gets bounded capacity so queued activity cannot starve
            # expired deliveries. Incomplete legacy envelopes are quarantined.
            values: list[str] = []
            for state in ("pending", "delivering"):
                field = "available_at" if state == "pending" else "lease_until"
                query = root.where(filter=FieldFilter("state", "==", state))
                query = query.where(filter=FieldFilter(field, "<=", at)).limit(limit // 2)
                values.extend(row.id for row in query.stream())
            return values
        except Exception as exc:
            raise SourceUnavailable("activity queue unavailable") from exc

    def claim(self, event_id: str, owner: str, at: datetime) -> OutboxLease | None:
        ref = self.client.collection("outbox").document(event_id)

        @firestore.transactional
        def write(transaction: Any) -> OutboxLease | None:
            value = ref.get(transaction=transaction).to_dict() or {}
            state = value.get("state")
            due = value.get("available_at") if state == "pending" else value.get("lease_until")
            if state not in {"pending", "delivering"} or (due is not None and due > at):
                return None
            try:
                event = read_event(value)
                if event.event_id != event_id:
                    raise ValueError("event document identity mismatch")
            except (ValueError, KeyError, TypeError):
                transaction.update(ref, {"state": "quarantined", "error_code": "invalid_envelope"})
                return None
            attempt = int(value.get("attempt", 0)) + 1
            if attempt > 5:
                transaction.update(ref, {"state": "failed", "error_code": "attempts_exhausted"})
                return None
            fence = int(value.get("fence", 0)) + 1
            transaction.update(
                ref,
                {
                    "state": "delivering",
                    "owner": owner,
                    "fence": fence,
                    "attempt": attempt,
                    "lease_until": at + timedelta(seconds=90),
                },
            )
            return OutboxLease(event, owner, fence, attempt)

        result: OutboxLease | None = write(self.client.transaction())
        return result

    def _finish(self, lease: OutboxLease, at: datetime, success: bool) -> None:
        ref = self.client.collection("outbox").document(lease.event.event_id)

        @firestore.transactional
        def write(transaction: Any) -> None:
            current = ref.get(transaction=transaction).to_dict() or {}
            if (
                current.get("state") != "delivering"
                or current.get("owner") != lease.owner
                or current.get("fence") != lease.fence
                or current.get("lease_until", at) <= at
            ):
                raise LeaseLost("activity delivery lease lost")
            if success:
                transaction.update(ref, {"state": "delivered", "delivered_at": at})
            else:
                transaction.update(
                    ref,
                    {
                        "state": "failed" if lease.attempt >= 5 else "pending",
                        "error_code": "clickhouse_unavailable",
                        "available_at": at
                        + timedelta(seconds=min(300, 15 * 2 ** (lease.attempt - 1))),
                    },
                )

        write(self.client.transaction())

    def acknowledge(self, lease: OutboxLease, at: datetime) -> None:
        self._finish(lease, at, True)

    def fail(self, lease: OutboxLease, at: datetime) -> None:
        self._finish(lease, at, False)
