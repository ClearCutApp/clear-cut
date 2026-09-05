"""Unit tests for `AddBibleFacts` (`createBibleFact`,
`POST /api/projects/{project_id}/bible/facts`).

The server assigns `fact_id`, so the numbering is the behaviour under test:
a batch continues the project's sequence rather than restarting it, and the
whole batch reaches the index in one call so a partially written bible is not
a state the store can end up in.

Hand-written fakes for the one port (AGENT.md Section 5) -- no
`unittest.mock`, no network.
"""

import pytest

from clearcut.application.add_bible_facts import AddBibleFacts, FactDraft
from clearcut.application.ports import LoreStore
from clearcut.domain.bible import BibleFact, FactKind
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.script import Scene

_DRAFT = FactDraft(
    kind=FactKind.LORE,
    text="Mariana has never left the province.",
    source="bible.pdf p.4",
)


def _fact(fact_id: str) -> BibleFact:
    return BibleFact(
        fact_id=fact_id,
        kind=FactKind.LORE,
        text="Already recorded.",
        source="bible.pdf p.1",
    )


class RecordingLoreStore:
    """Records every `index` call whole, so a test can assert on how many
    calls happened as well as what they carried."""

    def __init__(self, facts: list[BibleFact] | None = None) -> None:
        self._facts = list(facts or [])
        self.index_calls: list[tuple[str, list[BibleFact | Scene]]] = []

    def index(self, project_id: str, records: list[BibleFact | Scene]) -> None:
        self.index_calls.append((project_id, list(records)))
        self._facts.extend(record for record in records if isinstance(record, BibleFact))

    def search(self, project_id: str, query: str, limit: int) -> list[BibleFact]:
        raise NotImplementedError

    def facts(self, project_id: str) -> list[BibleFact]:
        return list(self._facts)


class _UnavailableLoreStore:
    """`facts` fails the way the retrieval adapter does when the index is
    unreachable, before any write is attempted."""

    def __init__(self) -> None:
        self.index_calls: list[tuple[str, list[BibleFact | Scene]]] = []

    def index(self, project_id: str, records: list[BibleFact | Scene]) -> None:
        self.index_calls.append((project_id, list(records)))

    def search(self, project_id: str, query: str, limit: int) -> list[BibleFact]:
        raise NotImplementedError

    def facts(self, project_id: str) -> list[BibleFact]:
        raise SourceUnavailable("lore index unreachable")


class _WriteFailsLoreStore:
    """Reads answer; the write fails."""

    def index(self, project_id: str, records: list[BibleFact | Scene]) -> None:
        raise SourceUnavailable("lore index unreachable")

    def search(self, project_id: str, query: str, limit: int) -> list[BibleFact]:
        raise NotImplementedError

    def facts(self, project_id: str) -> list[BibleFact]:
        return []


class _PositionalOnlyLoreStore:
    """Parameter names differ from `LoreStore`'s, so a keyword call fails."""

    def __init__(self) -> None:
        self.index_calls: list[tuple[str, list[BibleFact | Scene]]] = []

    def index(self, a: str, b: list[BibleFact | Scene]) -> None:
        self.index_calls.append((a, list(b)))

    def search(self, a: str, b: str, c: int) -> list[BibleFact]:
        raise NotImplementedError

    def facts(self, a: str) -> list[BibleFact]:
        return []


# Each fake bound to its port by an annotated assignment (CP-012, D3).
_recording_conforms: LoreStore = RecordingLoreStore()
_unavailable_conforms: LoreStore = _UnavailableLoreStore()
_write_fails_conforms: LoreStore = _WriteFailsLoreStore()


def test_recording_lore_store_satisfies_the_lorestore_port() -> None:
    assert isinstance(_recording_conforms, LoreStore)


def test_the_first_fact_of_an_empty_bible_is_fact_001() -> None:
    use_case = AddBibleFacts(RecordingLoreStore())

    created = use_case.execute("prj-4f2a", [_DRAFT])

    assert [fact.fact_id for fact in created] == ["FACT-001"]


def test_execute_carries_each_drafts_kind_text_and_source_onto_the_fact() -> None:
    policy = FactDraft(
        kind=FactKind.POLICY,
        text="No brand may be shown unlicensed.",
        source="legal memo p.2",
    )
    use_case = AddBibleFacts(RecordingLoreStore())

    created = use_case.execute("prj-4f2a", [policy])

    assert created[0].kind == FactKind.POLICY
    assert created[0].text == "No brand may be shown unlicensed."
    assert created[0].source == "legal memo p.2"


def test_numbering_continues_the_projects_existing_sequence() -> None:
    store = RecordingLoreStore([_fact("FACT-001")])
    use_case = AddBibleFacts(store)

    created = use_case.execute(
        "prj-4f2a",
        [_DRAFT, FactDraft(kind=FactKind.POLICY, text="Second.", source="memo p.3")],
    )

    assert [fact.fact_id for fact in created] == ["FACT-002", "FACT-003"]


def test_ids_are_padded_to_three_digits() -> None:
    store = RecordingLoreStore([_fact("FACT-041")])
    use_case = AddBibleFacts(store)

    assert use_case.execute("prj-4f2a", [_DRAFT])[0].fact_id == "FACT-042"


def test_execute_returns_the_facts_in_draft_order() -> None:
    drafts = [
        FactDraft(kind=FactKind.LORE, text="First.", source="bible.pdf p.1"),
        FactDraft(kind=FactKind.LORE, text="Second.", source="bible.pdf p.2"),
        FactDraft(kind=FactKind.LORE, text="Third.", source="bible.pdf p.3"),
    ]
    use_case = AddBibleFacts(RecordingLoreStore())

    created = use_case.execute("prj-4f2a", drafts)

    assert [fact.text for fact in created] == ["First.", "Second.", "Third."]


def test_two_drafts_reach_the_index_in_exactly_one_call() -> None:
    store = RecordingLoreStore()
    use_case = AddBibleFacts(store)

    created = use_case.execute(
        "prj-4f2a",
        [_DRAFT, FactDraft(kind=FactKind.POLICY, text="Second.", source="memo p.3")],
    )

    assert store.index_calls == [("prj-4f2a", [created[0], created[1]])]


def test_an_empty_draft_list_is_refused_before_the_port_is_touched() -> None:
    """A write that writes nothing is a mistake in the request, not a silent
    success: `execute` must not even read the existing facts."""
    store = _UnavailableLoreStore()
    use_case = AddBibleFacts(store)

    with pytest.raises(ValueError):
        use_case.execute("prj-4f2a", [])

    assert store.index_calls == []


def test_blank_text_raises_the_domain_error_and_indexes_nothing() -> None:
    store = RecordingLoreStore()
    use_case = AddBibleFacts(store)

    with pytest.raises(ValueError):
        use_case.execute("prj-4f2a", [FactDraft(kind=FactKind.LORE, text="   ", source="memo")])

    assert store.index_calls == []


def test_a_blank_source_in_the_second_draft_indexes_neither_fact() -> None:
    """The whole batch is built before the write, so one bad draft leaves the
    bible untouched rather than half written."""
    store = RecordingLoreStore()
    use_case = AddBibleFacts(store)

    with pytest.raises(ValueError):
        use_case.execute(
            "prj-4f2a",
            [_DRAFT, FactDraft(kind=FactKind.LORE, text="Second.", source="  ")],
        )

    assert store.index_calls == []


def test_a_read_outage_propagates_and_indexes_nothing() -> None:
    store = _UnavailableLoreStore()
    use_case = AddBibleFacts(store)

    with pytest.raises(SourceUnavailable):
        use_case.execute("prj-4f2a", [_DRAFT])

    assert store.index_calls == []


def test_a_write_outage_propagates_rather_than_reporting_facts_that_were_not_stored() -> None:
    use_case = AddBibleFacts(_WriteFailsLoreStore())

    with pytest.raises(SourceUnavailable):
        use_case.execute("prj-4f2a", [_DRAFT])


def test_port_methods_are_called_positionally() -> None:
    """D15: a keyword call through this fake raises `TypeError`."""
    store = _PositionalOnlyLoreStore()
    use_case = AddBibleFacts(store)

    created = use_case.execute("prj-4f2a", [_DRAFT])

    assert store.index_calls == [("prj-4f2a", [created[0]])]
