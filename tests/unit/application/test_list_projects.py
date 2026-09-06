"""Unit tests for `ListProjects` (`listProjects`, `GET /api/projects`).

The SPA draws this list first, so the order is part of the behaviour: newest
first, and ties on `created_at` broken by `project_id` so two projects
created in the same second never swap places between two reads.

Hand-written fakes for the one port (AGENT.md Section 5) -- no
`unittest.mock`, no network.
"""

import pytest

from clearcut.application.list_projects import ListProjects
from clearcut.application.ports import ProjectStore
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.project import Project
from tests.unit.fakes import FakeProjectStore


def _project(project_id: str, created_at: str) -> Project:
    return Project(
        project_id=project_id,
        title=f"Project {project_id}",
        jurisdiction_code="AR",
        created_at=created_at,
    )


class _UnavailableProjectStore:
    """`all` fails the way the ClickHouse adapter does when the cluster is
    unreachable."""

    def save(self, project: Project) -> None:
        raise NotImplementedError

    def get(self, project_id: str) -> Project:
        raise NotImplementedError

    def all(self) -> list[Project]:
        raise SourceUnavailable("clickhouse unreachable")


class _PositionalOnlyProjectStore:
    """Parameter names differ from `ProjectStore`'s, so a keyword call fails."""

    def __init__(self, projects: list[Project]) -> None:
        self._projects = projects

    def save(self, a: Project) -> None:
        raise NotImplementedError

    def get(self, a: str) -> Project:
        raise NotImplementedError

    def all(self) -> list[Project]:
        return list(self._projects)


# Each fake bound to its port by an annotated assignment (CP-012, D3).
_store_conforms: ProjectStore = FakeProjectStore()
_unavailable_conforms: ProjectStore = _UnavailableProjectStore()


def test_fake_project_store_satisfies_the_projectstore_port() -> None:
    assert isinstance(_store_conforms, ProjectStore)


def test_execute_returns_the_newest_project_first() -> None:
    older = _project("prj-a", "2026-09-01T00:00:00Z")
    newer = _project("prj-b", "2026-09-05T00:00:00Z")
    use_case = ListProjects(FakeProjectStore([older, newer]))

    assert use_case.execute() == [newer, older]


def test_projects_created_in_the_same_second_are_ordered_by_project_id() -> None:
    same_second = "2026-09-05T12:00:00Z"
    second = _project("prj-b", same_second)
    first = _project("prj-a", same_second)
    use_case = ListProjects(FakeProjectStore([second, first]))

    assert use_case.execute() == [first, second]


def test_the_order_does_not_depend_on_the_order_the_store_returned() -> None:
    """A total order means the same set answers the same way however the
    store happened to hand it over."""
    same_second = "2026-09-05T12:00:00Z"
    newest = _project("prj-c", "2026-09-06T00:00:00Z")
    tied_a = _project("prj-a", same_second)
    tied_b = _project("prj-b", same_second)

    forwards = ListProjects(FakeProjectStore([newest, tied_a, tied_b])).execute()
    backwards = ListProjects(FakeProjectStore([tied_b, tied_a, newest])).execute()

    assert forwards == backwards == [newest, tied_a, tied_b]


def test_an_empty_store_returns_an_empty_list() -> None:
    use_case = ListProjects(FakeProjectStore())

    assert use_case.execute() == []


def test_a_store_outage_propagates_rather_than_answering_an_empty_list() -> None:
    """An empty list means "no projects yet"; a failed read must not be
    dressed up as one."""
    use_case = ListProjects(_UnavailableProjectStore())

    with pytest.raises(SourceUnavailable):
        use_case.execute()


def test_execute_calls_all_without_arguments() -> None:
    """D15: `all` takes no arguments, so a fake with a different signature
    still proves the use case passes none."""
    projects = [_project("prj-a", "2026-09-01T00:00:00Z")]
    use_case = ListProjects(_PositionalOnlyProjectStore(projects))

    assert use_case.execute() == projects
