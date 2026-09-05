"""Unit tests for `GetProject` (`getProject`, `GET /api/projects/{project_id}`).

`ProjectStore.get` already raises `RecordNotFound` for an id nobody stored,
which the HTTP boundary maps to 404. This use case adds no lookup of its own,
so the failure test asserts that error arrives unchanged.

Hand-written fakes for the one port (AGENT.md Section 5) -- no
`unittest.mock`, no network.
"""

import pytest

from clearcut.application.get_project import GetProject
from clearcut.application.ports import ProjectStore
from clearcut.domain.errors import RecordNotFound, SourceUnavailable
from clearcut.domain.project import Project
from tests.unit.fakes import FakeProjectStore


def _project(project_id: str = "prj-4f2a") -> Project:
    return Project(
        project_id=project_id,
        title="El Ultimo Verano",
        jurisdiction_code="AR",
        created_at="2026-09-05T12:00:00Z",
    )


class _UnavailableProjectStore:
    """`get` fails the way the ClickHouse adapter does when the cluster is
    unreachable, which is not the same answer as "no such project"."""

    def save(self, project: Project) -> None:
        raise NotImplementedError

    def get(self, project_id: str) -> Project:
        raise SourceUnavailable("clickhouse unreachable")

    def all(self) -> list[Project]:
        raise NotImplementedError


class _PositionalOnlyProjectStore:
    """Parameter names differ from `ProjectStore`'s, so a keyword call fails."""

    def __init__(self, project: Project) -> None:
        self._project = project
        self.asked: list[str] = []

    def save(self, a: Project) -> None:
        raise NotImplementedError

    def get(self, a: str) -> Project:
        self.asked.append(a)
        return self._project

    def all(self) -> list[Project]:
        raise NotImplementedError


# Each fake bound to its port by an annotated assignment (CP-012, D3).
_store_conforms: ProjectStore = FakeProjectStore()
_unavailable_conforms: ProjectStore = _UnavailableProjectStore()


def test_fake_project_store_satisfies_the_projectstore_port() -> None:
    assert isinstance(_store_conforms, ProjectStore)


def test_execute_returns_the_stored_project() -> None:
    stored = _project()
    use_case = GetProject(FakeProjectStore([stored]))

    assert use_case.execute("prj-4f2a") == stored


def test_execute_returns_the_project_asked_for_not_the_first_one_stored() -> None:
    wanted = _project("prj-b")
    use_case = GetProject(FakeProjectStore([_project("prj-a"), wanted]))

    assert use_case.execute("prj-b") == wanted


def test_an_unknown_project_id_propagates_record_not_found() -> None:
    use_case = GetProject(FakeProjectStore())

    with pytest.raises(RecordNotFound):
        use_case.execute("prj-nobody")


def test_a_store_outage_propagates_as_itself_not_as_record_not_found() -> None:
    """A 502 and a 404 are different answers to a producer; swallowing the
    outage into `RecordNotFound` would tell them their project is gone."""
    use_case = GetProject(_UnavailableProjectStore())

    with pytest.raises(SourceUnavailable):
        use_case.execute("prj-4f2a")


def test_execute_calls_get_positionally() -> None:
    """D15: a keyword call through this fake raises `TypeError`."""
    store = _PositionalOnlyProjectStore(_project())
    use_case = GetProject(store)

    result = use_case.execute("prj-4f2a")

    assert store.asked == ["prj-4f2a"]
    assert result == _project()
