"""Unit tests for `GetScript` (docs/api/openapi.yaml,
`GET /api/projects/{project_id}/scripts/{script_id}`).

The span assertions here are about what `ScriptDetail.spans` carries -- one
scene's marks, every scene's marks in scene order, and nothing at all when a
`raw_text` is absent. Which characters a phrase claims, and which of two
overlapping findings wins them, is `domain/highlight.spans_for`'s contract and
is tested at tests/unit/domain/test_highlight.py; repeating it here would give
that rule a second owner.

Hand-written fakes only, no `unittest.mock`, no network (AGENT.md Section 5).
"""

import pytest

from clearcut.application.get_script import GetScript
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.finding import Category, Finding, NerLabel, RiskLevel
from clearcut.domain.script import Scene, Script
from tests.unit.fakes import FakeFindingStore, FakeScriptStore

_SCENE_ONE = Scene(
    number=1,
    heading="INT. BAR NOTTURNO - NIGHT",
    page_start=1,
    page_end=2,
    text="MARA drinks a Coca-Cola and says nothing.",
)
_SCENE_TWO = Scene(
    number=7,
    heading="EXT. AVENIDA CORRIENTES - DAY",
    page_start=9,
    page_end=9,
    text="A Coca-Cola billboard fills the frame.",
)


def _script(scenes: list[Scene]) -> Script:
    return Script(
        script_id="scr-77b1",
        project_id="prj-4f2a",
        version=2,
        gcs_uri="gs://clearcut-scripts/prj-4f2a/el-ultimo-verano-v2.pdf",
        jurisdiction_code="AR",
        scenes=scenes,
    )


def _finding(finding_id: str, raw_text: str, scene_number: int = 1) -> Finding:
    return Finding(
        finding_id=finding_id,
        scene_number=scene_number,
        page=1,
        raw_text=raw_text,
        category=Category.INDUSTRIAL_PROPERTY,
        ner_label=NerLabel.BRAND,
        risk_level=RiskLevel.HIGH,
        required_document="Brand clearance",
    )


def _stores(script: Script, findings: list[Finding]) -> tuple[FakeScriptStore, FakeFindingStore]:
    scripts = FakeScriptStore([script])
    finding_store = FakeFindingStore()
    finding_store.save(script.project_id, script.script_id, findings)
    return scripts, finding_store


def test_execute_returns_the_version_and_its_findings() -> None:
    script = _script([_SCENE_ONE])
    finding = _finding("EVT-014", "Coca-Cola")
    scripts, findings = _stores(script, [finding])

    detail = GetScript(scripts, findings).execute("prj-4f2a", "scr-77b1")

    assert detail.script == script
    assert detail.findings == (finding,)


def test_execute_marks_a_scene_that_contains_the_findings_raw_text() -> None:
    scripts, findings = _stores(_script([_SCENE_ONE]), [_finding("EVT-014", "Coca-Cola")])

    detail = GetScript(scripts, findings).execute("prj-4f2a", "scr-77b1")

    assert len(detail.spans) == 1
    span = detail.spans[0]
    assert span.finding_id == "EVT-014"
    assert span.scene_number == 1
    assert _SCENE_ONE.text[span.start : span.end] == "Coca-Cola"


def test_execute_marks_nothing_when_no_raw_text_appears_in_the_script() -> None:
    """The model paraphrased, or the scene changed between versions. The
    finding still reaches the rail; only the inline mark is absent."""
    scripts, findings = _stores(_script([_SCENE_ONE]), [_finding("EVT-021", "Pepsi")])

    detail = GetScript(scripts, findings).execute("prj-4f2a", "scr-77b1")

    assert detail.findings == (_finding("EVT-021", "Pepsi"),)
    assert detail.spans == ()


def test_execute_keeps_scene_order_across_the_spans_it_joins() -> None:
    """One finding covers every scene its asset appears in, so the spans of
    scene 7 follow the spans of scene 1 rather than being filtered away by
    the finding's own `scene_number`."""
    scripts, findings = _stores(
        _script([_SCENE_ONE, _SCENE_TWO]), [_finding("EVT-014", "Coca-Cola")]
    )

    detail = GetScript(scripts, findings).execute("prj-4f2a", "scr-77b1")

    assert [span.scene_number for span in detail.spans] == [1, 7]


def test_execute_marks_nothing_for_a_version_with_no_findings() -> None:
    scripts, findings = _stores(_script([_SCENE_ONE]), [])

    detail = GetScript(scripts, findings).execute("prj-4f2a", "scr-77b1")

    assert detail.findings == ()
    assert detail.spans == ()


def test_execute_propagates_record_not_found_for_an_unknown_script() -> None:
    scripts, findings = _stores(_script([_SCENE_ONE]), [])

    with pytest.raises(RecordNotFound, match="scr-0000"):
        GetScript(scripts, findings).execute("prj-4f2a", "scr-0000")


def test_execute_propagates_record_not_found_for_a_script_in_another_project() -> None:
    """A version belongs to one project; reading it through another is a
    404, not someone else's script."""
    scripts, findings = _stores(_script([_SCENE_ONE]), [])

    with pytest.raises(RecordNotFound, match="scr-77b1"):
        GetScript(scripts, findings).execute("prj-0000", "scr-77b1")
