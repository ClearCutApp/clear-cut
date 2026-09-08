"""Separate fenced outbox for committed-analysis scene projections."""

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from clearcut.application.lore_projection_ports import LoreLease
from clearcut.domain.durable_analysis import LeaseLost
from clearcut.domain.screenplay import ContentReference


class FirestoreLoreProjection:
    def __init__(self, client: Any) -> None:
        self.client = client

    def ready(self, at: datetime, limit: int = 10) -> list[str]:
        root = self.client.collection("lore_outbox")
        result: list[tuple[datetime, str]] = []
        for state, field in (("pending", "available_at"), ("delivering", "lease_until")):
            query = root.where(filter=FieldFilter("state", "==", state))
            result.extend(
                (row.to_dict()[field], row.id)
                for row in query.where(filter=FieldFilter(field, "<=", at))
                .order_by(field)
                .limit(max(1, limit // 2))
                .stream()
            )
        return [identifier for _, identifier in sorted(result)][:limit]

    def claim(self, analysis_id: str, owner: str, at: datetime) -> LoreLease | None:
        ref = self.client.collection("lore_outbox").document(analysis_id)

        @firestore.transactional
        def write(tx: Any) -> LoreLease | None:
            value = ref.get(transaction=tx).to_dict() or {}
            state = value.get("state")
            deadline = value.get("available_at") if state == "pending" else value.get("lease_until")
            if state not in {"pending", "delivering"} or deadline is None or deadline > at:
                return None
            attempt = int(value.get("attempt", 0)) + 1
            if attempt > 5:
                tx.update(ref, {"state": "failed", "error_code": "attempts_exhausted"})
                return None
            fence = int(value.get("fence", 0)) + 1
            try:
                if any(
                    not isinstance(value.get(key), str) or not value[key]
                    for key in (
                        "organization_id",
                        "project_id",
                        "revision_id",
                        "provider_config_json",
                    )
                ):
                    raise ValueError("invalid projection identity")
                lease = LoreLease(
                    analysis_id,
                    value["organization_id"],
                    value["project_id"],
                    value["revision_id"],
                    ContentReference(**value["manifest"]),
                    value["provider_config_json"],
                    owner,
                    fence,
                    int(value.get("cursor", 0)),
                    ContentReference(**value["checkpoint"]) if value.get("checkpoint") else None,
                )
                if lease.cursor < 0:
                    raise ValueError("invalid projection cursor")
            except (ValueError, KeyError, TypeError):
                tx.update(ref, {"state": "failed", "error_code": "invalid_envelope"})
                return None
            tx.update(
                ref,
                {
                    "state": "delivering",
                    "owner": owner,
                    "fence": fence,
                    "attempt": attempt,
                    "lease_until": at + timedelta(seconds=90),
                },
            )
            return lease

        result: LoreLease | None = write(self.client.transaction())
        return result

    def _update(self, lease: LoreLease, at: datetime, changes: dict[str, Any]) -> None:
        ref = self.client.collection("lore_outbox").document(lease.analysis_id)

        @firestore.transactional
        def write(tx: Any) -> None:
            value = ref.get(transaction=tx).to_dict() or {}
            if (
                value.get("state") != "delivering"
                or value.get("owner") != lease.owner
                or value.get("fence") != lease.fence
                or value.get("cursor", 0) != lease.cursor
                or value.get("lease_until", at) <= at
            ):
                raise LeaseLost("lore projection lease lost")
            tx.update(ref, changes)

        write(self.client.transaction())

    def heartbeat(self, lease: LoreLease, at: datetime) -> None:
        self._update(lease, at, {"lease_until": at + timedelta(seconds=90)})

    def checkpoint(self, lease: LoreLease, content: ContentReference, at: datetime) -> None:
        self._update(lease, at, {"checkpoint": asdict(content)})

    def advance(self, lease: LoreLease, cursor: int, complete: bool, at: datetime) -> None:
        if cursor < lease.cursor:
            raise ValueError("projection cursor cannot move backwards")
        self._update(
            lease,
            at,
            {
                "cursor": cursor,
                "state": "ready" if complete else "pending",
                "available_at": at,
                "checkpoint": None,
                "attempt": 0,
                "completed_at": at if complete else None,
            },
        )

    def fail(self, lease: LoreLease, at: datetime) -> None:
        self._update(
            lease,
            at,
            {
                "state": "pending",
                "available_at": at + timedelta(seconds=60),
                "error_code": "projection_unavailable",
            },
        )

    def current(self, project_id: str) -> dict[str, Any]:
        project = (
            self.client.collection("project_access").document(project_id).get().to_dict() or {}
        )
        analysis_id = project.get("committed_analysis_id")
        if not analysis_id:
            return {"state": "not_analyzed"}
        value = self.client.collection("lore_outbox").document(analysis_id).get().to_dict() or {}
        if value.get("project_id") != project_id or value.get("organization_id") != project.get(
            "organization_id"
        ):
            return {"state": "not_indexed", "analysis_id": analysis_id}
        return {"analysis_id": analysis_id, **value}
