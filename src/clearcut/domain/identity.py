"""Verified identities and private project permissions."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Identity:
    user_id: str
    email: str


class AuthenticationRequired(Exception):
    """Missing, expired, revoked or unverified identity."""


class AccessDenied(Exception):
    """No active membership and explicit project grant for this action."""


def permits(role: str, action: str) -> bool:
    permissions = {
        "owner": {"read", "produce", "write", "manage", "script"},
        "admin": {"read", "produce", "write", "manage", "script"},
        "producer": {"read", "produce", "script"},
        "writer": {"read", "write", "script"},
        "viewer": {"read"},
    }
    return action in permissions.get(role, set())


def project_permits(
    scope: dict[str, Any], member: dict[str, Any], user_id: str, action: str
) -> bool:
    """Rejoining an organization never revives grants from an older membership."""
    member_epoch = int(member.get("membership_epoch", 1))
    grant_epoch = int(scope.get("grant_epochs", {}).get(user_id, 1))
    return (
        member.get("active") is True
        and member_epoch == grant_epoch
        and permits(str(member.get("role", "")), "read")
        and permits(str(scope.get("grants", {}).get(user_id, "")), action)
    )
