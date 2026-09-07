"""Transactional team changes and single-use, verified-email invitations."""

import re
from datetime import datetime, timedelta
from typing import Any

from google.cloud import firestore

from clearcut.domain.identity import AccessDenied, Identity, permits, project_permits
from clearcut.domain.workspace import (
    PROJECT_ROLES,
    ROLES,
    InvalidWorkspace,
    WorkspaceConflict,
    identifier,
)


class FirestoreTeams:
    def __init__(self, client: Any) -> None:
        self.client = client

    def _org(self, organization_id: str) -> Any:
        return self.client.collection("organizations").document(identifier(organization_id))

    def _manage(
        self, transaction: Any, actor: str, organization_id: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        org = self._org(organization_id)
        metadata = org.get(transaction=transaction).to_dict() or {}
        member = (
            org.collection("members").document(actor).get(transaction=transaction).to_dict() or {}
        )
        if (
            not metadata
            or member.get("active") is not True
            or not permits(str(member.get("role", "")), "manage")
        ):
            raise AccessDenied("workspace management unavailable")
        return metadata, member

    def members(self, actor: str, organization_id: str) -> list[dict[str, Any]]:
        @firestore.transactional
        def authorize(transaction: Any) -> None:
            self._manage(transaction, actor, organization_id)

        authorize(self.client.transaction())
        return [
            {"user_id": row.id, **row.to_dict()}
            for row in self._org(organization_id).collection("members").stream()
        ]

    def invitations(self, actor: str, organization_id: str) -> list[dict[str, Any]]:
        @firestore.transactional
        def authorize(transaction: Any) -> None:
            self._manage(transaction, actor, organization_id)

        authorize(self.client.transaction())
        return [
            {key: value for key, value in row.to_dict().items() if key != "token_hash"}
            for row in self._org(organization_id).collection("invitations").stream()
        ]

    def invite(
        self,
        actor: str,
        organization_id: str,
        invitation_id: str,
        token_hash: str,
        email: str,
        role: str,
        at: datetime,
    ) -> dict[str, Any]:
        if (
            role not in PROJECT_ROLES
            or not isinstance(email, str)
            or len(email) > 254
            or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip())
        ):
            raise InvalidWorkspace("provide an email and valid invitation role")
        email = email.strip().casefold()
        org = self._org(organization_id)
        invitation = {
            "invitation_id": identifier(invitation_id),
            "email": email,
            "role": role,
            "created_by": actor,
            "created_at": at,
            "expires_at": at + timedelta(days=7),
            "state": "pending",
            "version": 1,
            "token_hash": token_hash,
        }

        @firestore.transactional
        def write(transaction: Any) -> None:
            self._manage(transaction, actor, organization_id)
            transaction.create(org.collection("invitations").document(invitation_id), invitation)
            transaction.create(
                self.client.collection("invitation_tokens").document(token_hash),
                {"organization_id": organization_id, "invitation_id": invitation_id},
            )
            transaction.create(
                org.collection("events").document("invitation-" + invitation_id),
                {
                    "kind": "invitation_created",
                    "actor": actor,
                    "invitation_id": invitation_id,
                    "role": role,
                    "at": at,
                },
            )

        write(self.client.transaction())
        return {key: value for key, value in invitation.items() if key != "token_hash"}

    def accept(self, identity: Identity, token_hash: str, at: datetime) -> str:
        @firestore.transactional
        def write(transaction: Any) -> str:
            lookup = (
                self.client.collection("invitation_tokens")
                .document(token_hash)
                .get(transaction=transaction)
                .to_dict()
                or {}
            )
            if not lookup:
                raise InvalidWorkspace("invitation is unavailable")
            org = self._org(lookup["organization_id"])
            ref = org.collection("invitations").document(lookup["invitation_id"])
            invitation = ref.get(transaction=transaction).to_dict() or {}
            metadata = org.get(transaction=transaction).to_dict() or {}
            member_ref = org.collection("members").document(identity.user_id)
            member = member_ref.get(transaction=transaction).to_dict() or {}
            inviter = (
                org.collection("members")
                .document(invitation.get("created_by", "_"))
                .get(transaction=transaction)
                .to_dict()
                or {}
            )
            if (
                invitation.get("state") == "accepted"
                and invitation.get("accepted_by") == identity.user_id
                and member.get("active") is True
            ):
                return str(lookup["organization_id"])
            if (
                invitation.get("state") != "pending"
                or invitation.get("expires_at", at) <= at
                or invitation.get("email") != identity.email.strip().casefold()
                or inviter.get("active") is not True
                or not permits(str(inviter.get("role", "")), "manage")
            ):
                raise InvalidWorkspace("invitation is expired, revoked or belongs to another email")
            if member.get("active") is True:
                updated = member
            else:
                updated = {
                    "active": True,
                    "role": invitation["role"],
                    "email": identity.email,
                    "version": int(member.get("version", 0)) + 1,
                    "membership_epoch": int(member.get("membership_epoch", 1)) + 1 if member else 1,
                }
                transaction.set(member_ref, updated)
            transaction.set(
                self.client.collection("users")
                .document(identity.user_id)
                .collection("organizations")
                .document(lookup["organization_id"]),
                {"name": str(metadata.get("name", ""))},
            )
            transaction.update(
                ref,
                {
                    "state": "accepted",
                    "accepted_by": identity.user_id,
                    "accepted_at": at,
                    "version": int(invitation["version"]) + 1,
                },
            )
            transaction.create(
                org.collection("events").document("accepted-" + lookup["invitation_id"]),
                {
                    "kind": "invitation_accepted",
                    "actor": identity.user_id,
                    "invitation_id": lookup["invitation_id"],
                    "at": at,
                },
            )
            # Joining creates no project grant or project index.
            return str(lookup["organization_id"])

        return str(write(self.client.transaction()))

    def revoke_invitation(
        self,
        actor: str,
        organization_id: str,
        invitation_id: str,
        expected_version: int,
        at: datetime,
    ) -> None:
        org = self._org(organization_id)
        ref = org.collection("invitations").document(identifier(invitation_id))

        @firestore.transactional
        def write(transaction: Any) -> None:
            self._manage(transaction, actor, organization_id)
            value = ref.get(transaction=transaction).to_dict() or {}
            if value.get("version") != expected_version or value.get("state") != "pending":
                raise WorkspaceConflict("invitation changed")
            transaction.update(
                ref, {"state": "revoked", "version": expected_version + 1, "revoked_at": at}
            )
            transaction.create(
                org.collection("events").document(
                    f"invitation-revoked-{invitation_id}-{expected_version + 1}"
                ),
                {
                    "kind": "invitation_revoked",
                    "actor": actor,
                    "invitation_id": invitation_id,
                    "version": expected_version + 1,
                    "at": at,
                },
            )

        write(self.client.transaction())

    def change_member(
        self,
        actor: str,
        organization_id: str,
        user_id: str,
        role: str,
        active: bool,
        expected_version: int,
        at: datetime,
    ) -> None:
        if role not in ROLES or type(active) is not bool:
            raise InvalidWorkspace("invalid member role or active state")
        org = self._org(organization_id)
        target = org.collection("members").document(identifier(user_id))

        @firestore.transactional
        def write(transaction: Any) -> None:
            metadata, manager = self._manage(transaction, actor, organization_id)
            member = target.get(transaction=transaction).to_dict() or {}
            if int(member.get("version", 1)) != expected_version or not member:
                raise WorkspaceConflict("membership changed")
            if not member.get("active") and active:
                raise InvalidWorkspace("use a new invitation to restore membership")
            owners = set(metadata.get("owner_ids") or [metadata.get("owner_id")])
            owners.discard(None)
            if (member.get("role") == "owner" or role == "owner") and manager.get(
                "role"
            ) != "owner":
                raise AccessDenied("only owners can change owner membership")
            if member.get("role") == "owner" and (not active or role != "owner"):
                owners.discard(user_id)
            if active and role == "owner":
                owners.add(user_id)
            if not owners:
                raise InvalidWorkspace("keep at least one active workspace owner")
            transaction.update(
                target, {"role": role, "active": active, "version": expected_version + 1}
            )
            transaction.update(
                org,
                {
                    "owner_ids": sorted(owners),
                    "team_version": int(metadata.get("team_version", 0)) + 1,
                },
            )
            transaction.create(
                org.collection("events").document(f"member-{user_id}-{expected_version + 1}"),
                {
                    "kind": "member_changed",
                    "actor": actor,
                    "user_id": user_id,
                    "role": role,
                    "active": active,
                    "version": expected_version + 1,
                    "at": at,
                },
            )

        write(self.client.transaction())

    def project_members(self, actor: str, project_id: str) -> dict[str, Any]:
        project = self.client.collection("project_access").document(identifier(project_id))

        @firestore.transactional
        def read(transaction: Any) -> dict[str, Any]:
            scope = project.get(transaction=transaction).to_dict() or {}
            org = self._org(scope.get("organization_id", "_"))
            member = (
                org.collection("members").document(actor).get(transaction=transaction).to_dict()
                or {}
            )
            if not project_permits(scope, member, actor, "read"):
                raise AccessDenied()
            values = []
            for user_id, role in scope.get("grants", {}).items():
                candidate = (
                    org.collection("members")
                    .document(user_id)
                    .get(transaction=transaction)
                    .to_dict()
                    or {}
                )
                if project_permits(scope, candidate, user_id, "read"):
                    values.append(
                        {"user_id": user_id, "role": role, "email": candidate.get("email", "")}
                    )
            return {
                "organization_id": scope["organization_id"],
                "version": int(scope.get("access_version", 1)),
                "can_manage": permits(str(member.get("role", "")), "manage")
                and permits(str(scope.get("grants", {}).get(actor, "")), "manage"),
                "can_edit": project_permits(scope, member, actor, "produce"),
                "members": values,
            }

        result: dict[str, Any] = read(self.client.transaction())
        return result

    def assign(
        self,
        actor: str,
        project_id: str,
        user_id: str,
        role: str | None,
        expected_version: int,
        at: datetime,
    ) -> None:
        identifier(user_id)
        if role is not None and role not in PROJECT_ROLES:
            raise InvalidWorkspace("invalid project role")
        project = self.client.collection("project_access").document(identifier(project_id))

        @firestore.transactional
        def write(transaction: Any) -> None:
            scope = project.get(transaction=transaction).to_dict() or {}
            organization_id = scope.get("organization_id", "_")
            _, manager = self._manage(transaction, actor, organization_id)
            if not project_permits(scope, manager, actor, "manage"):
                raise AccessDenied("project management requires explicit access")
            member = (
                self._org(organization_id)
                .collection("members")
                .document(user_id)
                .get(transaction=transaction)
                .to_dict()
                or {}
            )
            if int(scope.get("access_version", 1)) != expected_version:
                raise WorkspaceConflict("project access changed")
            if role is not None and member.get("active") is not True:
                raise InvalidWorkspace("assign only an active member of this workspace")
            grants = dict(scope.get("grants", {}))
            epochs = dict(scope.get("grant_epochs", {}))
            if role is None:
                grants.pop(user_id, None)
                epochs.pop(user_id, None)
            else:
                grants[user_id] = role
                epochs[user_id] = int(member.get("membership_epoch", 1))
            if not any(permits(value, "manage") for value in grants.values()):
                raise InvalidWorkspace("keep at least one project manager")
            transaction.update(
                project,
                {"grants": grants, "grant_epochs": epochs, "access_version": expected_version + 1},
            )
            transaction.set(
                self.client.collection("users")
                .document(user_id)
                .collection("projects")
                .document(project_id),
                {"organization_id": organization_id, "revoked": role is None},
            )
            transaction.create(
                project.collection("access_events").document(str(expected_version + 1)),
                {
                    "actor": actor,
                    "user_id": user_id,
                    "role": role,
                    "version": expected_version + 1,
                    "at": at,
                },
            )

        write(self.client.transaction())
