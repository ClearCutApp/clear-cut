"""Identity verification and authorization storage boundaries."""

from typing import Protocol

from clearcut.domain.identity import Identity
from clearcut.domain.project import Project


class IdentityVerifier(Protocol):
    def verify(self, token: str) -> Identity: ...


class ProjectAccess(Protocol):
    def authorize(self, user_id: str, project_id: str, action: str) -> str:
        """Return organization ID only after active membership and explicit grant."""
        ...

    def visible_project_ids(self, user_id: str) -> set[str]: ...
    def get_project(self, project_id: str) -> Project: ...
    def create_project(self, user_id: str, organization_id: str, project: Project) -> None: ...
    def create_organization(self, user_id: str, organization_id: str, name: str) -> None: ...
    def organizations(self, user_id: str) -> list[dict[str, str]]: ...


class ProjectFavourites(Protocol):
    """One user's bookmarked projects.

    Separate from `ProjectAccess` because a favourite is not an authorization
    fact and not a fact about the project either: two users disagree about it
    for the same project, which is precisely why it never went on the
    `Project` aggregate.
    """

    def favourites(self, user_id: str) -> set[str]:
        """The project ids this user has marked, as candidates only.

        Never a grant. A caller shows the marker only on a project it was
        already allowed to serve, the same way `visible_project_ids` treats
        the per-user index it reads.
        """
        ...

    def add_favourite(self, user_id: str, project_id: str) -> None:
        """Mark a project this user can read, or refuse the whole call."""
        ...

    def remove_favourite(self, user_id: str, project_id: str) -> None: ...


class OwnedFiles(Protocol):
    def register_file(self, project_id: str, file_id: str, uri: str) -> None: ...
    def resolve_file(self, project_id: str, file_id: str) -> str: ...
