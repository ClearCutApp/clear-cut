"""Immutable project research, authorized and bound to saved location settings."""

from dataclasses import asdict
from datetime import datetime
from typing import Any

from google.cloud import firestore

from clearcut.application.local_research_ports import LocalResearchSnapshot
from clearcut.application.ports import GroundedAnswer
from clearcut.domain.identity import AccessDenied, project_permits
from clearcut.domain.workspace import InvalidWorkspace, WorkspaceConflict


class FirestoreLocalResearch:
    def __init__(self, client: Any) -> None:
        self.client = client

    def list(self, project_id: str) -> list[dict[str, Any]]:
        records = (
            self.client.collection("project_access")
            .document(project_id)
            .collection("local_research")
        )
        return [
            record.to_dict()
            for record in records.order_by("created_at", direction="DESCENDING").limit(50).stream()
        ]

    def capture(self, project_id: str) -> LocalResearchSnapshot:
        ref = self.client.collection("project_access").document(project_id)

        @firestore.transactional
        def read(transaction: Any) -> LocalResearchSnapshot:
            scope = ref.get(transaction=transaction).to_dict() or {}
            records = (
                ref.collection("local_research")
                .order_by("created_at", direction="DESCENDING")
                .limit(50)
            )
            return LocalResearchSnapshot(
                int(scope.get("local_research_epoch", 0)),
                int(scope.get("settings_version", 1)),
                scope.get("production_context_json", "{}"),
                [value.to_dict() for value in records.stream(transaction=transaction)],
            )

        result: LocalResearchSnapshot = read(self.client.transaction())
        return result

    def save(
        self,
        project_id: str,
        actor: str,
        research_id: str,
        expected_settings_version: int,
        location_index: int,
        question: str,
        answer: GroundedAnswer,
        at: datetime,
    ) -> dict[str, Any]:
        scope_ref = self.client.collection("project_access").document(project_id)
        project_ref = self.client.collection("projects").document(project_id)

        @firestore.transactional
        def write(transaction: Any) -> dict[str, Any]:
            scope = scope_ref.get(transaction=transaction).to_dict() or {}
            project = project_ref.get(transaction=transaction).to_dict() or {}
            member = (
                self.client.collection("organizations")
                .document(scope.get("organization_id", "_"))
                .collection("members")
                .document(actor)
                .get(transaction=transaction)
                .to_dict()
                or {}
            )
            if not project_permits(scope, member, actor, "produce"):
                raise AccessDenied("production research permission required")
            if int(project.get("settings_version", 1)) != expected_settings_version:
                raise WorkspaceConflict("production settings changed while researching")
            locations = project.get("locations", [])
            if not 0 <= location_index < len(locations):
                raise InvalidWorkspace("select a saved production location")
            record = {
                "research_id": research_id,
                "project_id": project_id,
                "organization_id": scope["organization_id"],
                "actor": actor,
                "created_at": at,
                "settings_version": expected_settings_version,
                "location": locations[location_index],
                "question": question,
                "text": answer.text,
                "citations": [asdict(c) for c in answer.citations],
                "status": "evidence_found" if answer.citations else "coverage_gap",
                "human_clearance": False,
                "provider": "Parallel Search",
            }
            transaction.create(scope_ref.collection("local_research").document(research_id), record)
            transaction.update(
                scope_ref, {"local_research_epoch": int(scope.get("local_research_epoch", 0)) + 1}
            )
            return record

        result: dict[str, Any] = write(self.client.transaction())
        return result
