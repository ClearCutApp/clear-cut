"""Unit tests for `GetBible` (`getProjectBible`,
`GET /api/projects/{project_id}/bible`).

The wire contract says the response carries an empty `facts` array when
nothing has been recorded, so an unwritten bible is a 200 with no facts
rather than a 404.

Hand-written fakes for the one port (AGENT.md Section 5) -- no
`unittest.mock`, no network.
"""

import pytest

from clearcut.application.get_bible import GetBible
from clearcut.application.ports import LoreStore
from clearcut.domain.bible import BibleFact, FactKind, ProjectBible
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.script import Scene
from tests.unit.fakes import FakeLoreStore


def _fact(fact_id: str, text: str = "Mariana has never left the province.") -> BibleFact:
    return BibleFact(fact_id=fact_id, kind=FactKind.LORE, text=text, source="bible.pdf p.4")


class _FixedLoreStore:
    """Returns exactly the fact list it was given, including a list the
    `FakeLoreStore` could never build."""

    def __init__(self, facts: list[BibleFact]) -> None:
        self._facts = facts

    def index(self, project_id: str, records: list[BibleFact | Scene]) -> None:
        raise NotImplementedError

    def search(self, project_id: str, query: str, limit: int) -> list[BibleFact]:
        raise NotImplementedError

    def facts(self, project_id: str) -> list[BibleFact]:
        return list(self._facts)


class _UnavailableLoreStore:
    """`facts` fails the way the retrieval adapter does when the index is
    unreachable."""

    def index(self, project_id: str, records: list[BibleFact | Scene]) -> None:
        raise NotImplementedError

    def search(self, project_id: str, query: str, limit: int) -> list[BibleFact]:
        raise NotImplementedError

    def facts(self, project_id: str) -> list[BibleFact]:
        raise SourceUnavailable("lore index unreachable")


class _PositionalOnlyLoreStore:
    """Parameter names differ from `LoreStore`'s, so a keyword call fails."""

    def __init__(self, facts: list[BibleFact]) -> None:
        self._facts = facts
        self.asked: list[str] = []

    def index(self, a: str, b: list[BibleFact | Scene]) -> None:
        raise NotImplementedError

    def search(self, a: str, b: str, c: int) -> list[BibleFact]:
        raise NotImplementedError

    def facts(self, a: str) -> list[BibleFact]:
        self.asked.append(a)
        return list(self._facts)


# Each fake bound to its port by an annotated assignment (CP-012, D3).
_store_conforms: LoreStore = FakeLoreStore()
_fixed_conforms: LoreStore = _FixedLoreStore([])
_unavailable_conforms: LoreStore = _UnavailableLoreStore()


def test_fake_lore_store_satisfies_the_lorestore_port() -> None:
    assert isinstance(_store_conforms, LoreStore)


def test_execute_returns_the_projects_facts_in_the_order_the_store_gave_them() -> None:
    facts = [_fact("FACT-001"), _fact("FACT-002", "The lighthouse burned in 1998.")]
    use_case = GetBible(_FixedLoreStore(facts))

    assert use_case.execute("prj-4f2a") == ProjectBible(
        project_id="prj-4f2a", facts=(facts[0], facts[1])
    )


def test_execute_returns_a_tuple_of_facts_not_the_stores_list() -> None:
    """`ProjectBible.facts` is a tuple, so a caller holding the bible cannot
    mutate what the store handed over."""
    use_case = GetBible(_FixedLoreStore([_fact("FACT-001")]))

    assert isinstance(use_case.execute("prj-4f2a").facts, tuple)


def test_a_project_with_nothing_recorded_returns_an_empty_bible() -> None:
    use_case = GetBible(FakeLoreStore())

    result = use_case.execute("prj-4f2a")

    assert result == ProjectBible(project_id="prj-4f2a", facts=())


def test_execute_only_reads_the_named_projects_facts() -> None:
    store = FakeLoreStore()
    records: list[BibleFact | Scene] = [_fact("FACT-001")]
    store.index("prj-other", records)
    use_case = GetBible(store)

    assert use_case.execute("prj-4f2a").facts == ()


def test_a_duplicate_fact_id_propagates_the_domain_error() -> None:
    """`ProjectBible.__post_init__` rejects a repeated `fact_id`; a bible
    that quietly dropped one would hide a corrupt index from the producer."""
    use_case = GetBible(_FixedLoreStore([_fact("FACT-001"), _fact("FACT-001", "Different text.")]))

    with pytest.raises(ValueError):
        use_case.execute("prj-4f2a")


def test_a_store_outage_propagates_rather_than_answering_an_empty_bible() -> None:
    use_case = GetBible(_UnavailableLoreStore())

    with pytest.raises(SourceUnavailable):
        use_case.execute("prj-4f2a")


def test_execute_calls_facts_positionally() -> None:
    """D15: a keyword call through this fake raises `TypeError`."""
    store = _PositionalOnlyLoreStore([_fact("FACT-001")])
    use_case = GetBible(store)

    result = use_case.execute("prj-4f2a")

    assert store.asked == ["prj-4f2a"]
    assert result.project_id == "prj-4f2a"
