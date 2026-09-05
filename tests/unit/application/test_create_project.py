"""Unit tests for `CreateProject` (`createProject`, `POST /api/projects`).

Hand-written fakes for the one port (AGENT.md Section 5) -- no
`unittest.mock`, no network, no clock read: `at` arrives as an argument.

`Project.__post_init__` owns the validation, so the tests below assert the
domain error reaches the caller *and* that nothing was written on the way
out: a rejected create must leave the store as it was.
"""

import pytest

from clearcut.application.create_project import CreateProject
from clearcut.application.ports import ProjectStore
from clearcut.domain.errors import UnknownJurisdiction
from clearcut.domain.jurisdiction import Jurisdiction, jurisdiction_for
from clearcut.domain.project import Project
from tests.unit.fakes import FakeProjectStore

_AT = "2026-09-05T12:00:00Z"
_AR = jurisdiction_for("AR")


class _PositionalOnlyProjectStore:
    """Parameter names differ from `ProjectStore`'s, so a keyword call fails."""

    def __init__(self) -> None:
        self.saved: list[Project] = []

    def save(self, a: Project) -> None:
        self.saved.append(a)

    def get(self, a: str) -> Project:
        raise NotImplementedError

    def all(self) -> list[Project]:
        return list(self.saved)


# Each fake bound to its port by an annotated assignment (CP-012, D3).
_store_conforms: ProjectStore = FakeProjectStore()
_positional_conforms: ProjectStore = _PositionalOnlyProjectStore()


def test_fake_project_store_satisfies_the_projectstore_port() -> None:
    assert isinstance(_store_conforms, ProjectStore)


def test_execute_returns_the_project_it_built() -> None:
    use_case = CreateProject(FakeProjectStore())

    result = use_case.execute("prj-4f2a", "El Ultimo Verano", _AR, _AT)

    assert result == Project(
        project_id="prj-4f2a",
        title="El Ultimo Verano",
        jurisdiction_code="AR",
        created_at=_AT,
    )


def test_execute_stores_the_project_under_its_own_id() -> None:
    store = FakeProjectStore()
    use_case = CreateProject(store)

    created = use_case.execute("prj-4f2a", "El Ultimo Verano", _AR, _AT)

    assert store.get("prj-4f2a") == created


def test_execute_records_the_jurisdictions_code_not_the_object() -> None:
    """`Project` carries `jurisdiction_code`; the lookup belongs to the
    domain's `jurisdiction_for`, so the use case stores the code alone."""
    use_case = CreateProject(FakeProjectStore())

    result = use_case.execute("prj-4f2a", "El Ultimo Verano", jurisdiction_for("MX"), _AT)

    assert result.jurisdiction_code == "MX"


def test_a_blank_title_raises_the_domain_error_and_stores_nothing() -> None:
    store = FakeProjectStore()
    use_case = CreateProject(store)

    with pytest.raises(ValueError):
        use_case.execute("prj-4f2a", "   ", _AR, _AT)

    assert store.all() == []


def test_a_blank_project_id_raises_the_domain_error_and_stores_nothing() -> None:
    store = FakeProjectStore()
    use_case = CreateProject(store)

    with pytest.raises(ValueError):
        use_case.execute("", "El Ultimo Verano", _AR, _AT)

    assert store.all() == []


def test_an_unknown_jurisdiction_code_raises_and_stores_nothing() -> None:
    """`Jurisdiction` is a plain value object with no validation of its own,
    so a hand-built one carrying an unlisted code reaches `Project`, which
    rejects it through `jurisdiction_for`."""
    store = FakeProjectStore()
    use_case = CreateProject(store)

    with pytest.raises(UnknownJurisdiction):
        use_case.execute("prj-4f2a", "El Ultimo Verano", Jurisdiction("ZZ", "Nowhere", "zz/"), _AT)

    assert store.all() == []


def test_execute_calls_save_positionally() -> None:
    """D15: a keyword call through this fake raises `TypeError`."""
    store = _PositionalOnlyProjectStore()
    use_case = CreateProject(store)

    created = use_case.execute("prj-4f2a", "El Ultimo Verano", _AR, _AT)

    assert store.saved == [created]
