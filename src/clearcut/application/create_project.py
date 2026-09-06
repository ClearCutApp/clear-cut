"""Creates one project (`createProject`, `POST /api/projects`).

No validation of its own: `Project.__post_init__` already refuses a blank id
or title and an unlisted jurisdiction code, and a second check here would be
a second owner of the same rule (AGENT.md Section 3, Information Expert).
Building the project before the save is what makes that rejection safe -- a
create the domain refuses writes nothing.

`at` arrives as an argument rather than being read from a clock, so this use
case stays testable without one (AGENT.md Section 2 rule 1).
"""

from clearcut.application.ports import ProjectStore
from clearcut.domain.jurisdiction import Jurisdiction
from clearcut.domain.project import Project


class CreateProject:
    """`CreateProject(projects)`."""

    def __init__(self, projects: ProjectStore) -> None:
        self._projects = projects

    def execute(self, project_id: str, title: str, jurisdiction: Jurisdiction, at: str) -> Project:
        project = Project(
            project_id=project_id,
            title=title,
            jurisdiction_code=jurisdiction.code,
            created_at=at,
        )
        self._projects.save(project)
        return project
