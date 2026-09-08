"""Firestore is authoritative for live project authorization.

A project_access document contains organization_id and grants {uid: role}.
An organization member document contains role and active. Neither an absent
legacy mapping nor organization membership alone grants project access.

Favourites hang off the user rather than the project, under
`users/{uid}/favourites/{project_id}`. A favourite is one person's opinion, so
storing it on the project would make it everybody's.
"""

from dataclasses import asdict
from typing import Any

from google.cloud import firestore

from clearcut.domain.activity import activity_envelope
from clearcut.domain.errors import RecordNotFound, SourceUnavailable
from clearcut.domain.identity import AccessDenied, permits, project_permits
from clearcut.domain.project import Project


class FirestoreProjectAccess:
    def __init__(self, client: Any) -> None:
        self._client = client

    def authorize(self, user_id: str, project_id: str, action: str) -> str:
        @firestore.transactional
        def check(transaction: Any) -> str:
            project = self._client.collection("project_access").document(project_id)
            data = project.get(transaction=transaction).to_dict() or {}
            organization = data.get("organization_id")
            if not isinstance(organization, str) or not organization:
                raise AccessDenied("project not found")
            member = (
                self._client.collection("organizations")
                .document(organization)
                .collection("members")
                .document(user_id)
            )
            membership = member.get(transaction=transaction).to_dict() or {}
            if not project_permits(data, membership, user_id, action):
                raise AccessDenied("project not found")
            return organization

        try:
            return str(check(self._client.transaction()))
        except AccessDenied:
            raise
        except Exception as exc:
            raise SourceUnavailable("workspace authorization unavailable") from exc

    def visible_project_ids(self, user_id: str) -> set[str]:
        # The per-user index narrows candidates only; each candidate is reauthorized.
        try:
            candidates = (
                self._client.collection("users").document(user_id).collection("projects").stream()
            )
            result: set[str] = set()
            for candidate in candidates:
                try:
                    self.authorize(user_id, candidate.id, "read")
                except AccessDenied:
                    continue
                result.add(candidate.id)
            return result
        except SourceUnavailable:
            raise
        except Exception as exc:
            raise SourceUnavailable("workspace authorization unavailable") from exc

    def register_file(self, project_id: str, file_id: str, uri: str) -> None:
        try:
            (
                self._client.collection("project_access")
                .document(project_id)
                .collection("files")
                .document(file_id)
                .create({"gcs_uri": uri})
            )
        except Exception as exc:
            raise SourceUnavailable("file registration unavailable") from exc

    def resolve_file(self, project_id: str, file_id: str) -> str:
        from clearcut.domain.errors import RecordNotFound

        if not file_id or "/" in file_id or "\\" in file_id:
            raise RecordNotFound("file not found")
        try:
            data = (
                self._client.collection("project_access")
                .document(project_id)
                .collection("files")
                .document(file_id)
                .get()
                .to_dict()
                or {}
            )
        except Exception as exc:
            raise SourceUnavailable("file lookup unavailable") from exc
        uri = data.get("gcs_uri")
        if not isinstance(uri, str) or not uri.startswith("gs://"):
            raise RecordNotFound("file not found")
        return uri

    def create_organization(self, user_id: str, organization_id: str, name: str) -> None:
        organization = self._client.collection("organizations").document(organization_id)
        index = (
            self._client.collection("users")
            .document(user_id)
            .collection("organizations")
            .document(organization_id)
        )
        batch = self._client.batch()
        batch.create(
            organization,
            {"name": name, "owner_id": user_id, "owner_ids": [user_id], "team_version": 1},
        )
        batch.create(
            organization.collection("members").document(user_id),
            {"active": True, "role": "owner", "version": 1, "membership_epoch": 1},
        )
        batch.create(index, {"name": name})
        try:
            batch.commit()
        except Exception as exc:
            raise SourceUnavailable("workspace creation unavailable") from exc

    def organizations(self, user_id: str) -> list[dict[str, str]]:
        try:
            indexes = (
                self._client.collection("users")
                .document(user_id)
                .collection("organizations")
                .stream()
            )
            result = []
            for index in indexes:
                ref = self._client.collection("organizations").document(index.id)
                member = ref.collection("members").document(user_id).get().to_dict() or {}
                if member.get("active") is True:
                    organization = ref.get().to_dict() or {}
                    result.append(
                        {
                            "organization_id": index.id,
                            "name": str(organization.get("name", "")),
                            "role": str(member.get("role", "")),
                        }
                    )
            return result
        except Exception as exc:
            raise SourceUnavailable("workspace lookup unavailable") from exc

    def get_project(self, project_id: str) -> Project:
        try:
            data = self._client.collection("projects").document(project_id).get().to_dict()
        except Exception as exc:
            raise SourceUnavailable("project lookup unavailable") from exc
        if not data:
            raise RecordNotFound("project not found")
        return Project(
            project_id=project_id,
            title=data["title"],
            jurisdiction_code=data["jurisdiction_code"],
            created_at=data["created_at"],
            # `.get`, not `[...]`: a document written before these three
            # existed carries none of them, and an unset poster is a real
            # answer rather than a corrupt record.
            poster_uri=data.get("poster_uri"),
            format=data.get("format"),
            status=data.get("status"),
        )

    def create_project(self, user_id: str, organization_id: str, project: Project) -> None:
        @firestore.transactional
        def create(transaction: Any) -> None:
            org = self._client.collection("organizations").document(organization_id)
            membership = org.collection("members").document(user_id)
            member = membership.get(transaction=transaction).to_dict() or {}
            if member.get("active") is not True or not permits(
                str(member.get("role", "")), "produce"
            ):
                raise AccessDenied("workspace does not allow project creation")
            transaction.create(
                self._client.collection("projects").document(project.project_id), asdict(project)
            )
            transaction.create(
                self._client.collection("project_access").document(project.project_id),
                {
                    "organization_id": organization_id,
                    "grants": {user_id: "owner"},
                    "grant_epochs": {user_id: int(member.get("membership_epoch", 1))},
                    "access_version": 1,
                    "settings_version": 1,
                },
            )
            transaction.create(
                self._client.collection("users")
                .document(user_id)
                .collection("projects")
                .document(project.project_id),
                {"organization_id": organization_id},
            )
            transaction.create(
                self._client.collection("outbox").document("project-" + project.project_id),
                activity_envelope(
                    "project-" + project.project_id,
                    organization_id,
                    project.project_id,
                    "project_created",
                    project.created_at,
                    1,
                    {"jurisdiction_code": project.jurisdiction_code},
                ),
            )

        try:
            create(self._client.transaction())
        except AccessDenied:
            raise
        except Exception as exc:
            raise SourceUnavailable("project creation unavailable") from exc

    # `ProjectFavourites` (`application/workspace_ports.py`). The marker is
    # one document per favourited project under the user, not an array on the
    # user: two tabs marking two projects at once then write two documents
    # instead of racing over one field, and the read below is the same
    # per-user `stream()` `visible_project_ids` already does.
    def _favourites(self, user_id: str) -> Any:
        return self._client.collection("users").document(user_id).collection("favourites")

    def favourites(self, user_id: str) -> set[str]:
        try:
            return {marked.id for marked in self._favourites(user_id).stream()}
        except Exception as exc:
            raise SourceUnavailable("favourites unavailable") from exc

    def add_favourite(self, user_id: str, project_id: str) -> None:
        """Authorized before it is written, so a project id typed into the URL
        cannot be bookmarked -- and, because the bookmark comes back on the
        list read, cannot be used to confirm that the project exists."""
        self.authorize(user_id, project_id, "read")
        try:
            self._favourites(user_id).document(project_id).set({"project_id": project_id})
        except Exception as exc:
            raise SourceUnavailable("favourites unavailable") from exc

    def remove_favourite(self, user_id: str, project_id: str) -> None:
        """Not authorized: deleting your own bookmark is always allowed, and a
        user who has lost access to a project must still be able to clear it."""
        try:
            self._favourites(user_id).document(project_id).delete()
        except Exception as exc:
            raise SourceUnavailable("favourites unavailable") from exc
