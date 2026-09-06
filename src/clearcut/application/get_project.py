"""Reads one project (`getProject`, `GET /api/projects/{project_id}`).

Delegation and nothing else. `ProjectStore.get` raises `RecordNotFound` for
an id nobody stored, which the HTTP boundary already maps to 404, so catching
it here would only replace that answer with a worse one.

It exists as a use case rather than the route holding `ProjectStore` because
`adapters/http/routes.py` takes use-case instances and nothing else
(CHECKPOINTS.md Decision D30).
"""

from clearcut.application.ports import ProjectStore
from clearcut.domain.project import Project


class GetProject:
    """`GetProject(projects)`."""

    def __init__(self, projects: ProjectStore) -> None:
        self._projects = projects

    def execute(self, project_id: str) -> Project:
        return self._projects.get(project_id)
