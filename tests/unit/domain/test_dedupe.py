"""Tests for dedupe_findings (docs/plan/sdd.md Section 4.1 step 4)."""

from typing import Any

from clearcut.domain.dedupe import dedupe_findings
from clearcut.domain.finding import Category, Finding, NerLabel, RiskLevel


def _finding(**overrides: Any) -> Finding:
    fields: dict[str, Any] = dict(
        finding_id="EVT-001",
        scene_number=1,
        page=1,
        raw_text="Quilmes",
        category=Category.INDUSTRIAL_PROPERTY,
        ner_label=NerLabel.BRAND,
        risk_level=RiskLevel.MEDIUM,
        required_document="Trademark Clearance Form",
    )
    fields.update(overrides)
    return Finding(**fields)


def test_empty_input_returns_empty_list():
    assert dedupe_findings([]) == []


def test_two_findings_for_the_same_asset_collapse_into_one_entry():
    first = _finding(finding_id="EVT-001", scene_number=2)
    second = _finding(finding_id="EVT-002", scene_number=5)

    result = dedupe_findings([first, second])

    assert result == [(first, (2, 5))]


def test_fourteen_scenes_of_one_brand_collapse_to_one_entry_with_fourteen_scenes():
    findings = [_finding(finding_id=f"EVT-{n:03d}", scene_number=n) for n in range(1, 15)]

    result = dedupe_findings(findings)

    assert len(result) == 1
    survivor, scenes = result[0]
    assert survivor == findings[0]
    assert scenes == tuple(range(1, 15))


def test_same_raw_text_under_different_categories_stay_separate():
    industrial = _finding(
        finding_id="EVT-001",
        category=Category.INDUSTRIAL_PROPERTY,
        ner_label=NerLabel.BRAND,
        raw_text="Ferrari",
    )
    visual = _finding(
        finding_id="EVT-002",
        category=Category.INTEGRATED_VISUAL,
        ner_label=NerLabel.PROPS_DESIGN,
        raw_text="Ferrari",
    )

    result = dedupe_findings([industrial, visual])

    assert result == [(industrial, (1,)), (visual, (1,))]


def test_order_is_first_appearance_and_scene_numbers_ascend():
    ferrari = _finding(finding_id="EVT-001", raw_text="Ferrari", scene_number=3)
    quilmes = _finding(finding_id="EVT-002", raw_text="Quilmes", scene_number=1)
    ferrari_again = _finding(finding_id="EVT-003", raw_text="Ferrari", scene_number=2)

    result = dedupe_findings([ferrari, quilmes, ferrari_again])

    assert [survivor.raw_text for survivor, _ in result] == ["Ferrari", "Quilmes"]
    assert result[0][1] == (2, 3)
    assert result[1][1] == (1,)


def test_surviving_finding_is_the_first_one_seen_unchanged():
    first = _finding(finding_id="EVT-001", scene_number=1, page=10)
    second = _finding(finding_id="EVT-002", scene_number=2, page=99)

    result = dedupe_findings([first, second])

    assert result[0][0] is first
    assert result[0][0] == first


def test_two_findings_in_the_same_scene_collapse_to_one_scene_number():
    first = _finding(finding_id="EVT-001", scene_number=7)
    second = _finding(finding_id="EVT-002", scene_number=7)
    third = _finding(finding_id="EVT-003", scene_number=9)

    result = dedupe_findings([first, second, third])

    assert result[0][1] == (7, 9)


def test_asset_repeated_three_times_in_one_scene_returns_a_single_element_tuple():
    findings = [_finding(finding_id=f"EVT-{n:03d}", scene_number=4) for n in range(3)]

    result = dedupe_findings(findings)

    assert result[0][1] == (4,)


def test_findings_differing_only_in_case_and_spacing_collapse_together():
    first = _finding(finding_id="EVT-001", raw_text="  A Bottle of  Quilmes  ", scene_number=1)
    second = _finding(finding_id="EVT-002", raw_text="a bottle of quilmes", scene_number=2)

    result = dedupe_findings([first, second])

    assert len(result) == 1
    assert result[0] == (first, (1, 2))
