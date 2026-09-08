"""Human clearance survives only matching scene/content/context applicability."""

from dataclasses import replace

from clearcut.application.analysis_documents import finding_data
from clearcut.application.reconcile_analysis import reconcile_analysis
from clearcut.domain.tracker import TrackerState
from tests.unit.application.test_analyze_script import _AT, _MEXICO, _scene, _use_case


def test_reordering_stable_scene_preserves_clearance_but_changed_content_requires_review():
    report = _use_case().calculate(
        "project", "script", 1, "gs://revision", _MEXICO, _AT, [_scene()]
    )
    anchors = [{"scene_number": 1, "scene_id": "stable-scene", "content_digest": "unchanged"}]
    findings, items, bindings = reconcile_analysis(
        report, [], None, anchors, "revision-1", "MX", _AT
    )
    human = replace(
        items[0],
        state=TrackerState.CLEARED,
        needs_review=False,
        version=2,
        note="Human permission",
        draft_email="Reviewed draft",
        evidence_file_ids=("proof",),
        clearance_conditions="Only Mexico",
        due_date="2026-09-08",
        assignee_id="producer",
    )
    previous = {
        "findings": [finding_data(finding) for finding in findings],
        "clearance_bindings": bindings,
    }
    reordered = replace(
        report,
        findings=(replace(report.findings[0], scene_number=2),),
        tracker_items=(replace(report.tracker_items[0], scene_numbers=(2,)),),
    )
    _, preserved, _ = reconcile_analysis(
        reordered, [human], previous, [{**anchors[0], "scene_number": 2}], "revision-2", "MX", _AT
    )
    assert preserved[0].state is TrackerState.CLEARED and not preserved[0].needs_review
    assert preserved[0].item_id == human.item_id and preserved[0].scene_numbers == (2,)
    _, changed, _ = reconcile_analysis(
        report,
        [human],
        previous,
        [{**anchors[0], "content_digest": "changed"}],
        "revision-3",
        "MX",
        _AT,
    )
    assert changed[0].needs_review and changed[0].state is TrackerState.CLEARED
    for field in (
        "note",
        "draft_email",
        "evidence_file_ids",
        "clearance_conditions",
        "due_date",
        "assignee_id",
    ):
        assert getattr(changed[0], field) == getattr(human, field)
    assert changed[0].version == human.version + 1


def test_removed_asset_is_carried_with_original_revision_and_review_required():
    report = _use_case().calculate(
        "project", "script", 1, "gs://revision", _MEXICO, _AT, [_scene()]
    )
    anchors = [{"scene_number": 1, "scene_id": "stable", "content_digest": "one"}]
    findings, items, bindings = reconcile_analysis(
        report, [], None, anchors, "revision-1", "MX", _AT
    )
    previous = {
        "findings": [finding_data(finding) for finding in findings],
        "clearance_bindings": bindings,
    }
    empty = replace(report, findings=(), tracker_items=())
    carried_findings, carried, next_bindings = reconcile_analysis(
        empty, items, previous, anchors, "revision-2", "MX", _AT
    )
    assert len(carried) == len(carried_findings) == 1 and carried[0].needs_review
    assert next_bindings[carried[0].item_id]["revision_id"] == "revision-1"
    assert next_bindings[carried[0].item_id]["present"] is False
