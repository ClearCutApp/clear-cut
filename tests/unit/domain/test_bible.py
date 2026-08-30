"""Tests for `clearcut.domain.bible` (CP-004)."""

import pytest

from clearcut.domain.bible import BibleFact, FactKind, ProjectBible


def test_facts_of_returns_only_matching_kind_in_insertion_order() -> None:
    policy_one = BibleFact(
        fact_id="F-3", kind=FactKind.POLICY, text="PG-13 tone only.", source="Style guide p. 5"
    )
    lore = BibleFact(
        fact_id="F-1", kind=FactKind.LORE, text="Ana lost an eye in 1990.", source="Bible p. 12"
    )
    policy_two = BibleFact(
        fact_id="F-2", kind=FactKind.POLICY, text="No on-screen smoking.", source="Style guide p. 3"
    )
    bible = ProjectBible(project_id="proj-1", facts=(policy_one, lore, policy_two))

    result = bible.facts_of(FactKind.POLICY)

    assert result == (policy_one, policy_two)


def test_facts_of_returns_empty_tuple_when_bible_holds_no_matching_kind() -> None:
    lore = BibleFact(
        fact_id="F-1", kind=FactKind.LORE, text="Ana lost an eye in 1990.", source="Bible p. 12"
    )
    bible = ProjectBible(project_id="proj-1", facts=(lore,))

    result = bible.facts_of(FactKind.POLICY)

    assert result == ()


def test_project_bible_defaults_to_no_facts() -> None:
    bible = ProjectBible(project_id="proj-1")

    assert bible.facts == ()


def test_blank_text_raises_value_error() -> None:
    with pytest.raises(ValueError, match="text"):
        BibleFact(fact_id="F-1", kind=FactKind.LORE, text="   ", source="Bible p. 12")


@pytest.mark.parametrize("blank_source", ["", "   "])
def test_blank_source_raises_value_error(blank_source: str) -> None:
    with pytest.raises(ValueError, match="source"):
        BibleFact(fact_id="F-1", kind=FactKind.LORE, text="Ana lost an eye.", source=blank_source)


def test_duplicate_fact_id_raises_value_error() -> None:
    first = BibleFact(
        fact_id="F-1", kind=FactKind.LORE, text="Ana lost an eye.", source="Bible p. 12"
    )
    second = BibleFact(
        fact_id="F-1", kind=FactKind.POLICY, text="No smoking.", source="Style guide p. 3"
    )

    with pytest.raises(ValueError, match="F-1"):
        ProjectBible(project_id="proj-1", facts=(first, second))
