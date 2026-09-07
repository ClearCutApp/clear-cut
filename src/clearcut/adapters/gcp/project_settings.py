"""Expected-version project settings and frozen production-location context."""

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

from google.cloud import firestore

from clearcut.domain.errors import RecordNotFound
from clearcut.domain.identity import AccessDenied, project_permits
from clearcut.domain.workspace import (
    LAUNCH_COUNTRIES,
    InvalidWorkspace,
    ProductionLocation,
    ProjectSettings,
    WorkspaceConflict,
)


class FirestoreProjectSettings:
    def __init__(self, client: Any) -> None:
        self.client = client

    def get(self, project_id: str) -> ProjectSettings:
        data = self.client.collection("projects").document(project_id).get().to_dict()
        if not data:
            raise RecordNotFound("project not found")
        return ProjectSettings(
            project_id,
            data["title"],
            data["jurisdiction_code"],
            int(data.get("settings_version", 1)),
            tuple(ProductionLocation(**value) for value in data.get("locations", [])),
        )

    def save(
        self, actor: str, settings: ProjectSettings, expected_version: int, at: datetime
    ) -> ProjectSettings:
        if (
            settings.version != expected_version + 1
            or settings.jurisdiction_code not in LAUNCH_COUNTRIES
        ):
            raise InvalidWorkspace("choose a launch country and the next settings version")
        scope_ref = self.client.collection("project_access").document(settings.project_id)
        project_ref = self.client.collection("projects").document(settings.project_id)

        @firestore.transactional
        def write(transaction: Any) -> ProjectSettings:
            scope = scope_ref.get(transaction=transaction).to_dict() or {}
            previous = project_ref.get(transaction=transaction).to_dict() or {}
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
                raise AccessDenied("project settings permission required")
            if int(previous.get("settings_version", 1)) != expected_version:
                raise WorkspaceConflict("project settings changed")
            locations = [asdict(value) for value in settings.locations]
            context = json.dumps(
                {"jurisdiction_code": settings.jurisdiction_code, "locations": locations},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            transaction.update(
                project_ref,
                {
                    "title": settings.title,
                    "jurisdiction_code": settings.jurisdiction_code,
                    "locations": locations,
                    "settings_version": settings.version,
                },
            )
            transaction.update(
                scope_ref,
                {"production_context_json": context, "settings_version": settings.version},
            )
            transaction.create(
                scope_ref.collection("settings_events").document(str(settings.version)),
                {
                    "actor": actor,
                    "at": at,
                    "version": settings.version,
                    "settings": asdict(settings),
                },
            )
            return settings

        result: ProjectSettings = write(self.client.transaction())
        return result
