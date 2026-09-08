"""Server-owned workspace management; organization membership grants no project."""

from datetime import datetime
from typing import Any, Protocol

from clearcut.domain.identity import Identity
from clearcut.domain.workspace import ProjectSettings


class WorkspaceManagement(Protocol):
    def members(self, actor: str, organization_id: str) -> list[dict[str, Any]]: ...
    def invitations(self, actor: str, organization_id: str) -> list[dict[str, Any]]: ...
    def invite(
        self,
        actor: str,
        organization_id: str,
        invitation_id: str,
        token_hash: str,
        email: str,
        role: str,
        at: datetime,
    ) -> dict[str, Any]: ...
    def accept(self, identity: Identity, token_hash: str, at: datetime) -> str: ...
    def revoke_invitation(
        self,
        actor: str,
        organization_id: str,
        invitation_id: str,
        expected_version: int,
        at: datetime,
    ) -> None: ...
    def change_member(
        self,
        actor: str,
        organization_id: str,
        user_id: str,
        role: str,
        active: bool,
        expected_version: int,
        at: datetime,
    ) -> None: ...
    def project_members(self, actor: str, project_id: str) -> dict[str, Any]: ...
    def assign(
        self,
        actor: str,
        project_id: str,
        user_id: str,
        role: str | None,
        expected_version: int,
        at: datetime,
    ) -> None: ...


class ProductionSettings(Protocol):
    def get(self, project_id: str) -> ProjectSettings: ...
    def save(
        self, actor: str, settings: ProjectSettings, expected_version: int, at: datetime
    ) -> ProjectSettings: ...
