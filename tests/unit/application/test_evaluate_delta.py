"""Unit tests for `EvaluateDelta` (CP-028, docs/plan/sdd.md Section 4.3, ADR 0007).

Hand-written fakes for all eight ports (AGENT.md Section 5) -- no
`unittest.mock`, no network, no clock read: `at` always arrives as an
argument. The fakes mirror `test_analyze_script.py`'s, extended with a
`Notifier` fake and a `_Tracker.latest_for_project`/`latest_script` that
actually hold state, since this use case reads both.
"""

from typing import Any

import pytest

from clearcut.application.analyze_script import AnalysisReport
from clearcut.application.evaluate_delta import EvaluateDelta, NoPreviousScriptVersion
from clearcut.application.grounding_query import _GROUNDING_TERMS
from clearcut.application.ports import (
    Confidence,
    ContinuityCheck,
    GroundedAnswer,
    LegalGrounding,
    LoreStore,
    Notifier,
    RightsClaim,
    RightsResearch,
    SceneExtractor,
    ScriptIngestion,
    TrackerStore,
)
from clearcut.domain.bible import BibleFact
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.finding import Category, Finding, NerLabel, RiskLevel
from clearcut.domain.jurisdiction import Jurisdiction, jurisdiction_for
from clearcut.domain.script import Scene, Script
from clearcut.domain.tracker import TrackerItem, TrackerState

_MEXICO = jurisdiction_for("MX")
_AT = "2026-08-31T00:00:00Z"


def _scene(
    number: int = 1, heading: str = "INT. BAR - DAY", text: str = "A neon sign glows."
) -> Scene:
    return Scene(number=number, heading=heading, page_start=number, page_end=number, text=text)


def _script(scenes: list[Scene], version: int = 1) -> Script:
    return Script(
        script_id="scr-1",
        project_id="proj-1",
        version=version,
        gcs_uri="gs://bucket/v1.pdf",
        jurisdiction_code=_MEXICO.code,
        scenes=scenes,
    )


def _finding(**overrides: Any) -> Finding:
    fields: dict[str, Any] = dict(
        finding_id="placeholder-uuid",
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


def _claim(**overrides: Any) -> RightsClaim:
    fields: dict[str, Any] = dict(
        holder="Cerveceria Quilmes",
        contact="legal@quilmes.example",
        litigation_posture="none on record",
        confidence=Confidence.HIGH,
    )
    fields.update(overrides)
    return RightsClaim(**fields)


def _item(**overrides: Any) -> TrackerItem:
    fields: dict[str, Any] = dict(
        item_id="EVT-001",
        project_id="proj-1",
        finding_id="EVT-001",
        scene_numbers=(1,),
        state=TrackerState.BLOCKED,
        required_document="Trademark Clearance Form",
        contact="legal@quilmes.example",
        litigation_posture="none on record",
        note="",
        updated_at="2026-08-30T00:00:00Z",
        version=1,
    )
    fields.update(overrides)
    return TrackerItem(**fields)


class _Ingestion:
    def __init__(self, scenes: list[Scene]) -> None:
        self._scenes = scenes

    def parse(self, gcs_uri: str, script_id: str) -> list[Scene]:
        return list(self._scenes)


class _Extractor:
    def __init__(self, findings: list[Finding] | None = None) -> None:
        self._findings = findings if findings is not None else []
        self.calls: list[list[Scene]] = []

    def extract(self, scenes: list[Scene], jurisdiction: Jurisdiction) -> list[Finding]:
        self.calls.append(list(scenes))
        return list(self._findings)


class _Grounding:
    def __init__(self, answer: GroundedAnswer | None = None) -> None:
        self._answer = answer if answer is not None else GroundedAnswer(text="", citations=())
        self.calls: list[tuple[str, Jurisdiction]] = []

    def ground(self, query: str, jurisdiction: Jurisdiction) -> GroundedAnswer:
        self.calls.append((query, jurisdiction))
        return self._answer


class _Research:
    def __init__(self, claim: RightsClaim | None = None) -> None:
        self._claim = claim if claim is not None else _claim()
        self.calls: list[tuple[str, Category, Jurisdiction]] = []

    def find(self, asset_name: str, category: Category, jurisdiction: Jurisdiction) -> RightsClaim:
        self.calls.append((asset_name, category, jurisdiction))
        return self._claim


class _LoreStore:
    def __init__(self, facts: list[BibleFact] | None = None) -> None:
        self._facts = facts if facts is not None else []
        self.indexed: list[tuple[str, list[BibleFact | Scene]]] = []
        self.searched: list[tuple[str, str, int]] = []

    def index(self, project_id: str, records: list[BibleFact | Scene]) -> None:
        self.indexed.append((project_id, list(records)))

    def search(self, project_id: str, query: str, limit: int) -> list[BibleFact]:
        self.searched.append((project_id, query, limit))
        return list(self._facts)


class _Continuity:
    def __init__(self, finding: Finding | None = None) -> None:
        self._finding = finding
        self.calls: list[Scene] = []

    def check(self, scene: Scene, facts: list[BibleFact]) -> Finding | None:
        self.calls.append(scene)
        return self._finding


class _Tracker:
    def __init__(
        self,
        script: Script | None = None,
        items: list[TrackerItem] | None = None,
        log: list[str] | None = None,
    ) -> None:
        self._script = script
        self._items = list(items) if items is not None else []
        self._log = log
        self.saved: list[list[TrackerItem]] = []
        self.recorded: list[Script] = []

    def save(self, items: list[TrackerItem]) -> None:
        if self._log is not None:
            self._log.append("tracker.save")
        self.saved.append(list(items))
        self._items.extend(items)

    def latest(self, project_id: str, item_id: str) -> TrackerItem:
        raise RecordNotFound(item_id)

    def latest_for_project(self, project_id: str) -> list[TrackerItem]:
        return [item for item in self._items if item.project_id == project_id]

    def record_script(self, script: Script) -> None:
        if self._log is not None:
            self._log.append("record_script")
        self.recorded.append(script)

    def latest_script(self, project_id: str) -> Script | None:
        if self._script is not None and self._script.project_id == project_id:
            return self._script
        return None


class _Notifier:
    def __init__(self) -> None:
        self.calls: list[tuple[TrackerItem, str]] = []

    def notify(self, item: TrackerItem, reason: str) -> None:
        self.calls.append((item, reason))


def _use_case(
    ingestion: _Ingestion | None = None,
    extractor: _Extractor | None = None,
    grounding: _Grounding | None = None,
    research: _Research | None = None,
    lore: _LoreStore | None = None,
    tracker: _Tracker | None = None,
    continuity: _Continuity | None = None,
    notifier: _Notifier | None = None,
) -> EvaluateDelta:
    return EvaluateDelta(
        ingestion=ingestion if ingestion is not None else _Ingestion([_scene()]),
        extractor=extractor if extractor is not None else _Extractor(),
        grounding=grounding if grounding is not None else _Grounding(),
        research=research if research is not None else _Research(),
        lore=lore if lore is not None else _LoreStore(),
        tracker=tracker if tracker is not None else _Tracker(_script([_scene()])),
        continuity=continuity if continuity is not None else _Continuity(),
        notifier=notifier if notifier is not None else _Notifier(),
    )


# Each fake bound to its port by an annotated assignment (CP-012, D3), before
# any `isinstance` narrowing.
_ingestion_conforms: ScriptIngestion = _Ingestion([])
_extractor_conforms: SceneExtractor = _Extractor([])
_grounding_conforms: LegalGrounding = _Grounding()
_research_conforms: RightsResearch = _Research()
_lore_conforms: LoreStore = _LoreStore()
_tracker_conforms: TrackerStore = _Tracker()
_continuity_conforms: ContinuityCheck = _Continuity()
_notifier_conforms: Notifier = _Notifier()


def test_fakes_satisfy_their_ports() -> None:
    assert isinstance(_ingestion_conforms, ScriptIngestion)
    assert isinstance(_extractor_conforms, SceneExtractor)
    assert isinstance(_grounding_conforms, LegalGrounding)
    assert isinstance(_research_conforms, RightsResearch)
    assert isinstance(_lore_conforms, LoreStore)
    assert isinstance(_tracker_conforms, TrackerStore)
    assert isinstance(_continuity_conforms, ContinuityCheck)
    assert isinstance(_notifier_conforms, Notifier)


def test_no_previous_version_raises_an_error_subclassing_record_not_found() -> None:
    use_case = _use_case(tracker=_Tracker(script=None))

    with pytest.raises(RecordNotFound):
        use_case.execute("proj-1", "scr-1", 2, "gs://bucket/v2.pdf", _MEXICO, _AT)


def test_no_previous_version_error_is_the_named_subclass() -> None:
    assert issubclass(NoPreviousScriptVersion, RecordNotFound)

    use_case = _use_case(tracker=_Tracker(script=None))

    with pytest.raises(NoPreviousScriptVersion):
        use_case.execute("proj-1", "scr-1", 2, "gs://bucket/v2.pdf", _MEXICO, _AT)


def test_unchanged_scenes_are_never_reextracted_or_reindexed() -> None:
    old_scenes = [
        _scene(1, text="unchanged text"),
        _scene(2, text="old text"),
        _scene(3, heading="INT. CUT - DAY", text="removed text"),
    ]
    new_scenes = [
        _scene(1, text="unchanged text"),
        _scene(2, text="new text"),
        _scene(4, heading="INT. NEW - DAY", text="added text"),
    ]
    tracker = _Tracker(
        script=_script(old_scenes),
        items=[
            _item(item_id="EVT-001", finding_id="EVT-001", scene_numbers=(1,)),
            _item(item_id="EVT-002", finding_id="EVT-002", scene_numbers=(2,)),
            _item(item_id="EVT-003", finding_id="EVT-003", scene_numbers=(3,)),
        ],
    )
    extractor = _Extractor(
        findings=[_finding(finding_id="uuid-a", raw_text="Quilmes", scene_number=2)]
    )
    lore = _LoreStore()
    use_case = _use_case(
        ingestion=_Ingestion(new_scenes), extractor=extractor, lore=lore, tracker=tracker
    )

    use_case.execute("proj-1", "scr-1", 2, "gs://bucket/v2.pdf", _MEXICO, _AT)

    assert len(extractor.calls) == 1
    assert {scene.number for scene in extractor.calls[0]} == {2, 4}
    assert len(lore.indexed) == 1
    indexed_scenes = [record for record in lore.indexed[0][1] if isinstance(record, Scene)]
    assert {scene.number for scene in indexed_scenes} == {2, 4}


def test_an_item_entirely_on_unchanged_scenes_carries_forward_without_a_save_call() -> None:
    old_scenes = [_scene(1, text="unchanged text")]
    new_scenes = [_scene(1, text="unchanged text")]
    unchanged_item = _item(item_id="EVT-001", finding_id="EVT-001", scene_numbers=(1,))
    tracker = _Tracker(script=_script(old_scenes), items=[unchanged_item])
    use_case = _use_case(ingestion=_Ingestion(new_scenes), tracker=tracker)

    report = use_case.execute("proj-1", "scr-1", 2, "gs://bucket/v2.pdf", _MEXICO, _AT)

    assert report.tracker_items == (unchanged_item,)
    assert tracker.saved == []


def test_removed_scene_keeps_its_tracker_item_open_with_a_note() -> None:
    old_scenes = [_scene(1), _scene(3, heading="INT. CUT - DAY", text="removed text")]
    new_scenes = [_scene(1)]
    removed_item = _item(
        item_id="EVT-003", finding_id="EVT-003", scene_numbers=(3,), state=TrackerState.BLOCKED
    )
    tracker = _Tracker(
        script=_script(old_scenes),
        items=[_item(item_id="EVT-001", finding_id="EVT-001", scene_numbers=(1,)), removed_item],
    )
    use_case = _use_case(ingestion=_Ingestion(new_scenes), tracker=tracker)

    report = use_case.execute("proj-1", "scr-1", 2, "gs://bucket/v2.pdf", _MEXICO, _AT)

    matches = [item for item in report.tracker_items if item.finding_id == "EVT-003"]
    assert len(matches) == 1
    kept = matches[0]
    assert kept.state == TrackerState.BLOCKED
    assert kept.note != ""
    assert kept.version == 2
    assert kept in tracker.saved[0]


def test_changed_scene_with_a_cleared_item_stays_cleared_but_flags_for_review_and_notifies() -> (
    None
):
    old_scenes = [_scene(2, text="old text")]
    new_scenes = [_scene(2, text="new text")]
    cleared_item = _item(
        item_id="EVT-002", finding_id="EVT-002", scene_numbers=(2,), state=TrackerState.CLEARED
    )
    tracker = _Tracker(script=_script(old_scenes), items=[cleared_item])
    extractor = _Extractor(
        findings=[_finding(finding_id="uuid-a", raw_text="Quilmes", scene_number=2)]
    )
    notifier = _Notifier()
    use_case = _use_case(
        ingestion=_Ingestion(new_scenes), extractor=extractor, tracker=tracker, notifier=notifier
    )

    report = use_case.execute("proj-1", "scr-1", 2, "gs://bucket/v2.pdf", _MEXICO, _AT)

    matches = [item for item in report.tracker_items if item.finding_id == "EVT-002"]
    assert len(matches) == 1
    updated = matches[0]
    assert updated.state == TrackerState.CLEARED
    assert updated.needs_review is True
    assert len(notifier.calls) == 1
    # The re-extracted finding returns under the matched item's finding_id,
    # not a freshly minted one -- distinguishes this outcome from the
    # moved-asset case, where no match survives and a fresh EVT id is minted
    # beside the stale item instead.
    assert len(report.findings) == 1
    assert report.findings[0].finding_id == "EVT-002"


def test_carry_forward_keeps_finding_id_when_the_asset_also_appears_in_an_added_scene() -> None:
    old_scenes = [_scene(2, text="old text")]
    new_scenes = [
        _scene(2, text="new text"),
        _scene(4, heading="INT. NEW - DAY", text="added text"),
    ]
    existing_item = _item(
        item_id="EVT-002", finding_id="EVT-002", scene_numbers=(2,), state=TrackerState.BLOCKED
    )
    tracker = _Tracker(script=_script(old_scenes), items=[existing_item])
    extractor = _Extractor(
        findings=[
            _finding(finding_id="uuid-a", raw_text="Quilmes", scene_number=2),
            _finding(finding_id="uuid-b", raw_text="Quilmes", scene_number=4),
        ]
    )
    use_case = _use_case(ingestion=_Ingestion(new_scenes), extractor=extractor, tracker=tracker)

    report = use_case.execute("proj-1", "scr-1", 2, "gs://bucket/v2.pdf", _MEXICO, _AT)

    assert len(report.findings) == 1
    assert report.findings[0].finding_id == "EVT-002"
    matches = [item for item in report.tracker_items if item.finding_id == "EVT-002"]
    assert len(matches) == 1
    assert matches[0].state == TrackerState.BLOCKED
    # Reused, not re-minted (D13-style stability across versions).
    assert matches[0] is existing_item


def test_a_newly_minted_item_spanning_a_changed_and_an_added_scene_carries_both_scene_numbers() -> (
    None
):
    """Criterion 2's collapse with no pre-existing item to match against: the
    asset is mentioned in both a CHANGED scene and a newly ADDED scene in the
    same upload, `dedupe_findings` (CP-019) collapses the two mentions before
    the lookup runs, and the minted item carries both scene numbers -- not
    just the first one dedupe_findings produced."""
    old_scenes = [_scene(2, text="old text")]
    new_scenes = [
        _scene(2, text="new text"),
        _scene(4, heading="INT. NEW - DAY", text="added text"),
    ]
    tracker = _Tracker(script=_script(old_scenes))
    extractor = _Extractor(
        findings=[
            _finding(finding_id="uuid-a", raw_text="Quilmes", scene_number=2),
            _finding(finding_id="uuid-b", raw_text="Quilmes", scene_number=4),
        ]
    )
    use_case = _use_case(ingestion=_Ingestion(new_scenes), extractor=extractor, tracker=tracker)

    report = use_case.execute("proj-1", "scr-1", 2, "gs://bucket/v2.pdf", _MEXICO, _AT)

    assert len(report.tracker_items) == 1
    assert report.tracker_items[0].scene_numbers == (2, 4)


def test_a_genuinely_new_asset_gets_the_next_evt_id_and_starts_blocked() -> None:
    old_scenes = [_scene(1)]
    new_scenes = [_scene(1), _scene(2, heading="INT. NEW - DAY", text="added text")]
    existing_item = _item(item_id="EVT-005", finding_id="EVT-005", scene_numbers=(1,))
    tracker = _Tracker(script=_script(old_scenes), items=[existing_item])
    extractor = _Extractor(
        findings=[_finding(finding_id="uuid-new", raw_text="Ferrari", scene_number=2)]
    )
    use_case = _use_case(ingestion=_Ingestion(new_scenes), extractor=extractor, tracker=tracker)

    report = use_case.execute("proj-1", "scr-1", 2, "gs://bucket/v2.pdf", _MEXICO, _AT)

    new_findings = [finding for finding in report.findings if finding.raw_text == "Ferrari"]
    assert len(new_findings) == 1
    assert new_findings[0].finding_id == "EVT-006"
    new_items = [item for item in report.tracker_items if item.finding_id == "EVT-006"]
    assert len(new_items) == 1
    assert new_items[0].state == TrackerState.BLOCKED
    assert new_items[0].version == 1


def test_a_cleared_item_on_a_changed_scene_flags_for_review_even_with_no_matching_finding() -> None:
    """ADR 0007's trigger is the CHANGED scene itself, not a re-extracted
    finding that happens to match: a CLEARED item whose scene changed but
    whose asset text disappeared entirely from the re-extraction still gets
    flagged and notified, never silently left CLEARED."""
    old_scenes = [_scene(2, text="Quilmes billboard")]
    new_scenes = [_scene(2, text="no brand mentioned anymore")]
    cleared_item = _item(
        item_id="EVT-002", finding_id="EVT-002", scene_numbers=(2,), state=TrackerState.CLEARED
    )
    tracker = _Tracker(script=_script(old_scenes), items=[cleared_item])
    notifier = _Notifier()
    use_case = _use_case(
        ingestion=_Ingestion(new_scenes),
        extractor=_Extractor(findings=[]),
        tracker=tracker,
        notifier=notifier,
    )

    report = use_case.execute("proj-1", "scr-1", 2, "gs://bucket/v2.pdf", _MEXICO, _AT)

    matches = [item for item in report.tracker_items if item.finding_id == "EVT-002"]
    assert len(matches) == 1
    assert matches[0].state == TrackerState.CLEARED
    assert matches[0].needs_review is True
    assert len(notifier.calls) == 1


def test_an_unmatched_candidate_on_a_changed_scene_keeps_its_open_item_with_a_note() -> None:
    old_scenes = [_scene(2, text="Quilmes billboard")]
    new_scenes = [_scene(2, text="no brand mentioned anymore")]
    existing_item = _item(
        item_id="EVT-002", finding_id="EVT-002", scene_numbers=(2,), state=TrackerState.BLOCKED
    )
    tracker = _Tracker(script=_script(old_scenes), items=[existing_item])
    use_case = _use_case(
        ingestion=_Ingestion(new_scenes), extractor=_Extractor(findings=[]), tracker=tracker
    )

    report = use_case.execute("proj-1", "scr-1", 2, "gs://bucket/v2.pdf", _MEXICO, _AT)

    matches = [item for item in report.tracker_items if item.finding_id == "EVT-002"]
    assert len(matches) == 1
    assert matches[0].state == TrackerState.BLOCKED
    assert matches[0].note != ""
    assert matches[0].version == 2


def test_a_moved_asset_leaves_a_fresh_blocked_item_and_a_flagged_noted_stale_item() -> None:
    """D37: the join is scene overlap, not asset identity, so an asset that
    moves to a different scene between versions does not carry its
    clearance. v1 scene 2 carries it as a CLEARED item; v2 edits it out of
    scene 2 and adds it in scene 9. Neither row is silent about it: the new
    item mints a fresh `EVT` id at BLOCKED, and the old item stays CLEARED,
    flagged for review, and carries a note naming the scene it was cleared
    against -- at exactly one version bump, not two."""
    old_scenes = [_scene(2, text="Quilmes billboard")]
    new_scenes = [
        _scene(2, text="no brand mentioned anymore"),
        _scene(9, heading="INT. GARAGE - DAY", text="Quilmes billboard"),
    ]
    stale_item = _item(
        item_id="EVT-002",
        finding_id="EVT-002",
        scene_numbers=(2,),
        state=TrackerState.CLEARED,
        version=3,
    )
    tracker = _Tracker(script=_script(old_scenes), items=[stale_item])
    extractor = _Extractor(
        findings=[_finding(finding_id="uuid-a", raw_text="Quilmes", scene_number=9)]
    )
    notifier = _Notifier()
    use_case = _use_case(
        ingestion=_Ingestion(new_scenes), extractor=extractor, tracker=tracker, notifier=notifier
    )

    report = use_case.execute("proj-1", "scr-1", 2, "gs://bucket/v2.pdf", _MEXICO, _AT)

    fresh_items = [item for item in report.tracker_items if item.scene_numbers == (9,)]
    assert len(fresh_items) == 1
    assert fresh_items[0].finding_id != "EVT-002"
    assert fresh_items[0].state == TrackerState.BLOCKED

    stale_matches = [item for item in report.tracker_items if item.finding_id == "EVT-002"]
    assert len(stale_matches) == 1
    stale = stale_matches[0]
    assert stale.state == TrackerState.CLEARED
    assert stale.needs_review is True
    assert "scene 2" in stale.note
    assert stale.version == 4


def test_record_script_is_called_once_with_the_runs_script_after_save() -> None:
    old_scenes = [_scene(1)]
    new_scenes = [_scene(1), _scene(2, heading="INT. NEW - DAY", text="added text")]
    log: list[str] = []
    tracker = _Tracker(script=_script(old_scenes), log=log)
    extractor = _Extractor(
        findings=[_finding(finding_id="uuid-new", raw_text="Ferrari", scene_number=2)]
    )
    use_case = _use_case(ingestion=_Ingestion(new_scenes), extractor=extractor, tracker=tracker)

    use_case.execute("proj-1", "scr-1", 2, "gs://bucket/v2.pdf", _MEXICO, _AT)

    assert len(tracker.recorded) == 1
    recorded = tracker.recorded[0]
    assert recorded.project_id == "proj-1"
    assert recorded.version == 2
    assert log.index("tracker.save") < log.index("record_script")


def test_execute_returns_an_analysis_report_carrying_script_findings_and_tracker_items() -> None:
    old_scenes = [_scene(1)]
    new_scenes = [_scene(1), _scene(2, heading="INT. NEW - DAY", text="added text")]
    tracker = _Tracker(script=_script(old_scenes))
    extractor = _Extractor(
        findings=[_finding(finding_id="uuid-new", raw_text="Ferrari", scene_number=2)]
    )
    use_case = _use_case(ingestion=_Ingestion(new_scenes), extractor=extractor, tracker=tracker)

    report = use_case.execute("proj-1", "scr-1", 2, "gs://bucket/v2.pdf", _MEXICO, _AT)

    assert isinstance(report, AnalysisReport)
    assert report.script.version == 2
    assert len(report.findings) >= 1
    assert len(report.tracker_items) >= 1


def test_execute_diffs_the_new_script_against_the_stored_latest_script() -> None:
    """`diff_scenes` joins against `tracker.latest_script(project_id)`: a
    scene identical to the stored version's is UNCHANGED and skipped, proven
    by `extract` never seeing it (already covered), while a scene that does
    not exist in the stored version at all is treated as ADDED and reaches
    `extract` -- so the comparison is against the stored script, not against
    an empty baseline."""
    old_scenes = [_scene(1, text="same text")]
    new_scenes = [_scene(1, text="same text"), _scene(2, heading="INT. NEW - DAY", text="new text")]
    tracker = _Tracker(script=_script(old_scenes))
    extractor = _Extractor(findings=[])
    use_case = _use_case(ingestion=_Ingestion(new_scenes), extractor=extractor, tracker=tracker)

    use_case.execute("proj-1", "scr-1", 2, "gs://bucket/v2.pdf", _MEXICO, _AT)

    assert {scene.number for scene in extractor.calls[0]} == {2}


def test_the_delta_grounding_query_never_contains_the_script_text() -> None:
    """The same defect `AnalyzeScript` had, duplicated inline here.

    `evaluate_delta.py` built its own copy of the query rather than sharing
    one, so fixing the pipeline left the delta path still searching for an enum
    name and a car model. Both now use `grounding_query`.
    """
    # A changed scene, so the delta path actually re-enriches. The default
    # fixture grounds nothing, which is what the first assertion below catches.
    old_scenes = [_scene(2, text="old text")]
    new_scenes = [_scene(2, text="new text")]
    grounding = _Grounding()
    use_case = _use_case(
        ingestion=_Ingestion(new_scenes),
        extractor=_Extractor(
            findings=[_finding(finding_id="uuid-a", raw_text="Quilmes", scene_number=2)]
        ),
        tracker=_Tracker(script=_script(old_scenes)),
        grounding=grounding,
    )

    use_case.execute("proj-1", "scr-2", 2, "gs://bucket/v2.pdf", _MEXICO, _AT)

    assert grounding.calls, "the delta path never grounded, so this proves nothing"
    for query, _ in grounding.calls:
        assert "clearance:" not in query
        assert query in set(_GROUNDING_TERMS.values())
