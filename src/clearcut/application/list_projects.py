"""Lists every project, newest first (`listProjects`, `GET /api/projects`).

The ordering lives here rather than in the store because it is what the
screen promises, not what ClickHouse happens to return: `created_at`
descending, ties broken by `project_id` ascending. Two projects created in
the same second therefore hold their places across reads instead of swapping
whenever a background merge reorders the rows.

Sorting twice is how Python spells that: `sorted` is stable, so the
`project_id` pass survives the `created_at` pass and both keys apply in the
direction each one needs.
"""

from clearcut.application.ports import ProjectStore
from clearcut.domain.project import Project


class ListProjects:
    """`ListProjects(projects)`."""

    def __init__(self, projects: ProjectStore) -> None:
        self._projects = projects

    def execute(self) -> list[Project]:
        by_id = sorted(self._projects.all(), key=lambda project: project.project_id)
        return sorted(by_id, key=lambda project: project.created_at, reverse=True)
