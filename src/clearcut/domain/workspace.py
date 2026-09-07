"""Workspace membership versions, invitations and production settings."""

from dataclasses import dataclass
from typing import Any

from clearcut.domain.errors import UnknownJurisdiction
from clearcut.domain.jurisdiction import jurisdiction_for


class WorkspaceConflict(Exception):
    """Membership, grants or project settings changed since the displayed version."""


class InvalidWorkspace(ValueError):
    """Invalid workspace management input."""


ROLES = frozenset({"owner", "admin", "producer", "writer", "viewer"})
PROJECT_ROLES = frozenset({"admin", "producer", "writer", "viewer"})
LAUNCH_COUNTRIES = frozenset({"AR", "MX", "ES", "CO", "US", "CA"})


def identifier(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 128 or "/" in value or "\\" in value:
        raise InvalidWorkspace("invalid identifier")
    return value


@dataclass(frozen=True)
class ProductionLocation:
    country: str
    location: str

    def __post_init__(self) -> None:
        if not isinstance(self.country, str) or self.country not in LAUNCH_COUNTRIES:
            raise InvalidWorkspace("production country is outside current launch coverage")
        if (
            not isinstance(self.location, str)
            or not self.location.strip()
            or len(self.location) > 500
        ):
            raise InvalidWorkspace("describe each production location in 1–500 characters")


@dataclass(frozen=True)
class ProjectSettings:
    project_id: str
    title: str
    jurisdiction_code: str
    version: int
    locations: tuple[ProductionLocation, ...] = ()

    def __post_init__(self) -> None:
        if not self.title.strip() or len(self.title) > 200:
            raise InvalidWorkspace("project title must contain 1–200 characters")
        try:
            if not isinstance(self.jurisdiction_code, str):
                raise InvalidWorkspace("invalid jurisdiction")
            jurisdiction_for(self.jurisdiction_code)
        except UnknownJurisdiction as exc:
            raise InvalidWorkspace("invalid jurisdiction") from exc
        if len(self.locations) > 30 or self.version < 1:
            raise InvalidWorkspace("invalid settings version or too many locations")


def membership_role(member: dict[str, Any]) -> str:
    return str(member.get("role", "")) if member.get("active") is True else ""
