"""Tests for Finding, RiskLevel, Category, NerLabel, and Citation (CP-003).

SDD reference: plan/sdd.md Section 2.
"""

import dataclasses
import enum

import pytest

from clearcut.domain.finding import Category, Citation, Finding, NerLabel, RiskLevel


def test_risk_level_is_a_str_enum_with_the_four_levels():
    assert issubclass(RiskLevel, enum.StrEnum)
    assert {level.value for level in RiskLevel} == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_category_is_a_str_enum_with_the_eight_sdd_categories():
    assert issubclass(Category, enum.StrEnum)
    assert {category.value for category in Category} == {
        "INDUSTRIAL_PROPERTY",
        "COPYRIGHT_WORKS",
        "PERSONALITY_IMAGE",
        "INTEGRATED_VISUAL",
        "LOCATIONS_PERMITS",
        "SPECIAL_SYMBOLS",
        "CONTINUITY",
        "POLICY",
    }


def test_ner_label_is_a_str_enum_with_the_eleven_tags():
    assert issubclass(NerLabel, enum.StrEnum)
    assert len(NerLabel) == 11


def test_citation_is_a_frozen_dataclass_with_uri_title_snippet():
    citation = Citation(uri="https://example.com/song", title="Song page", snippet="lyrics")
    assert citation.uri == "https://example.com/song"
    assert citation.title == "Song page"
    assert citation.snippet == "lyrics"
    with pytest.raises(dataclasses.FrozenInstanceError):
        citation.uri = "changed"


@pytest.mark.parametrize(
    "level,expected",
    [
        (RiskLevel.LOW, RiskLevel.MEDIUM),
        (RiskLevel.MEDIUM, RiskLevel.HIGH),
        (RiskLevel.HIGH, RiskLevel.CRITICAL),
        (RiskLevel.CRITICAL, RiskLevel.CRITICAL),
    ],
)
def test_risk_level_raised_steps_up_one_level_and_ceils_at_critical(level, expected):
    assert level.raised() == expected


def _finding(**overrides) -> Finding:
    fields = dict(
        finding_id="EVT-001",
        scene_number=4,
        page=12,
        raw_text="a bottle of Quilmes",
        category=Category.INDUSTRIAL_PROPERTY,
        ner_label=NerLabel.BRAND,
        risk_level=RiskLevel.MEDIUM,
        required_document="Trademark Clearance Form",
    )
    fields.update(overrides)
    return Finding(**fields)


def test_finding_carries_the_sdd_fields():
    citation = Citation(uri="https://example.com", title="Registry", snippet="entry")
    finding = _finding(citations=(citation,), contradicts=None)
    assert finding.finding_id == "EVT-001"
    assert finding.scene_number == 4
    assert finding.page == 12
    assert finding.raw_text == "a bottle of Quilmes"
    assert finding.category is Category.INDUSTRIAL_PROPERTY
    assert finding.ner_label is NerLabel.BRAND
    assert finding.risk_level is RiskLevel.MEDIUM
    assert finding.required_document == "Trademark Clearance Form"
    assert finding.citations == (citation,)
    assert finding.contradicts is None


def test_continuity_finding_with_a_ner_label_raises_value_error():
    with pytest.raises(ValueError, match="CONTINUITY"):
        _finding(category=Category.CONTINUITY, ner_label=NerLabel.BRAND)


def test_policy_finding_with_a_ner_label_raises_value_error():
    with pytest.raises(ValueError, match="POLICY"):
        _finding(category=Category.POLICY, ner_label=NerLabel.BRAND)


def test_continuity_finding_without_a_ner_label_is_valid():
    finding = _finding(
        category=Category.CONTINUITY,
        ner_label=None,
        contradicts="fact-001",
    )
    assert finding.ner_label is None
    assert finding.contradicts == "fact-001"
