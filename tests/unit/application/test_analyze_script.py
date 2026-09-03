"""Unit tests for `AnalyzeScript` (CP-026, docs/plan/sdd.md Section 4.1).

Hand-written fakes for all seven ports (AGENT.md Section 5) -- no
`unittest.mock`, no network, no clock read: `at` always arrives as an
argument. `NoGroundedSource` and `NoRightsHolderFound` are imported from
their adapter modules for realism only, the same precedent
`test_answer_project_question.py` set: that import is legal in `tests/`
because the layer guard restricts `src/clearcut/application`, not `tests/`.
"""

from typing import Any

import pytest

from clearcut.adapters.gcp.vertex_search import NoGroundedSource
from clearcut.adapters.parallel.research import NoRightsHolderFound
from clearcut.application.analyze_script import _NO_LOOKUP_CATEGORIES, AnalysisReport, AnalyzeScript
from clearcut.application.grounding_query import _GROUNDING_TERMS
from clearcut.application.ports import (
    Confidence,
    ContinuityCheck,
    GroundedAnswer,
    LegalGrounding,
    LoreStore,
    RightsClaim,
    RightsResearch,
    SceneExtractor,
    ScriptIngestion,
    TrackerStore,
)
from clearcut.domain.bible import BibleFact
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.finding import Category, Citation, Finding, NerLabel, RiskLevel
from clearcut.domain.jurisdiction import Jurisdiction, jurisdiction_for
from clearcut.domain.script import Scene, Script
from clearcut.domain.tracker import TrackerItem, TrackerState

_MEXICO = jurisdiction_for("MX")
_AT = "2026-08-31T00:00:00Z"


def _scene(number: int = 1, text: str = "INT. BAR - DAY\nA neon Quilmes sign glows.") -> Scene:
    return Scene(
        number=number, heading="INT. BAR - DAY", page_start=number, page_end=number, text=text
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


class _Ingestion:
    def __init__(
        self, scenes: list[Scene], error: Exception | None = None, log: list[str] | None = None
    ) -> None:
        self._scenes = scenes
        self._error = error
        self._log = log

    def parse(self, gcs_uri: str, script_id: str) -> list[Scene]:
        if self._log is not None:
            self._log.append("parse")
        if self._error is not None:
            raise self._error
        return list(self._scenes)


class _Extractor:
    def __init__(self, findings: list[Finding], log: list[str] | None = None) -> None:
        self._findings = findings
        self._log = log

    def extract(self, scenes: list[Scene], jurisdiction: Jurisdiction) -> list[Finding]:
        if self._log is not None:
            self._log.append("extract")
        return list(self._findings)


class _Grounding:
    """Returns `_answer` unless `finding.raw_text == raise_for`, which raises `_error`."""

    def __init__(
        self,
        answer: GroundedAnswer | None = None,
        raise_for: str | None = None,
        error: Exception | None = None,
        log: list[str] | None = None,
    ) -> None:
        self._answer = answer if answer is not None else GroundedAnswer(text="", citations=())
        self._raise_for = raise_for
        self._error = error
        self._log = log
        self.calls: list[tuple[str, Jurisdiction]] = []

    def ground(self, query: str, jurisdiction: Jurisdiction) -> GroundedAnswer:
        self.calls.append((query, jurisdiction))
        if self._log is not None:
            self._log.append("ground")
        if self._raise_for is not None and self._raise_for in query and self._error is not None:
            raise self._error
        return self._answer


class _Research:
    """Returns `_claim` unless `asset_name == raise_for`, which raises `_error`."""

    def __init__(
        self,
        claim: RightsClaim | None = None,
        raise_for: str | None = None,
        error: Exception | None = None,
        log: list[str] | None = None,
    ) -> None:
        self._claim = claim if claim is not None else _claim()
        self._raise_for = raise_for
        self._error = error
        self._log = log
        self.calls: list[tuple[str, Category, Jurisdiction]] = []

    def find(self, asset_name: str, category: Category, jurisdiction: Jurisdiction) -> RightsClaim:
        self.calls.append((asset_name, category, jurisdiction))
        if self._log is not None:
            self._log.append("research")
        if (
            self._raise_for is not None
            and asset_name == self._raise_for
            and self._error is not None
        ):
            raise self._error
        return self._claim


class _LoreStore:
    def __init__(self, facts: list[BibleFact] | None = None, log: list[str] | None = None) -> None:
        self._facts = facts if facts is not None else []
        self._log = log
        self.indexed: list[tuple[str, list[BibleFact | Scene]]] = []
        self.searched: list[tuple[str, str, int]] = []

    def index(self, project_id: str, records: list[BibleFact | Scene]) -> None:
        if self._log is not None:
            self._log.append("lore.index")
        self.indexed.append((project_id, list(records)))

    def search(self, project_id: str, query: str, limit: int) -> list[BibleFact]:
        if self._log is not None:
            self._log.append("lore.search")
        self.searched.append((project_id, query, limit))
        return list(self._facts)


class _Continuity:
    def __init__(self, finding: Finding | None = None, log: list[str] | None = None) -> None:
        self._finding = finding
        self._log = log
        self.calls: list[tuple[Scene, list[BibleFact]]] = []

    def check(self, scene: Scene, facts: list[BibleFact]) -> Finding | None:
        self.calls.append((scene, facts))
        if self._log is not None:
            self._log.append("continuity.check")
        return self._finding


class _Tracker:
    def __init__(self, log: list[str] | None = None) -> None:
        self._log = log
        self.saved: list[list[TrackerItem]] = []
        self.recorded: list[Script] = []

    def save(self, items: list[TrackerItem]) -> None:
        if self._log is not None:
            self._log.append("tracker.save")
        self.saved.append(list(items))

    def latest(self, item_id: str) -> TrackerItem:
        raise KeyError(item_id)

    def latest_for_project(self, project_id: str) -> list[TrackerItem]:
        return []

    def record_script(self, script: Script) -> None:
        if self._log is not None:
            self._log.append("record_script")
        self.recorded.append(script)

    def latest_script(self, project_id: str) -> Script | None:
        return None


def _use_case(
    scenes: list[Scene] | None = None,
    findings: list[Finding] | None = None,
    grounding: _Grounding | None = None,
    research: _Research | None = None,
    lore: _LoreStore | None = None,
    tracker: _Tracker | None = None,
    continuity: _Continuity | None = None,
    ingestion_error: Exception | None = None,
) -> AnalyzeScript:
    return AnalyzeScript(
        ingestion=_Ingestion(scenes if scenes is not None else [_scene()], error=ingestion_error),
        extractor=_Extractor(findings if findings is not None else [_finding()]),
        grounding=grounding if grounding is not None else _Grounding(),
        research=research if research is not None else _Research(),
        lore=lore if lore is not None else _LoreStore(),
        tracker=tracker if tracker is not None else _Tracker(),
        continuity=continuity if continuity is not None else _Continuity(),
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


def test_fakes_satisfy_their_ports() -> None:
    assert isinstance(_ingestion_conforms, ScriptIngestion)
    assert isinstance(_extractor_conforms, SceneExtractor)
    assert isinstance(_grounding_conforms, LegalGrounding)
    assert isinstance(_research_conforms, RightsResearch)
    assert isinstance(_lore_conforms, LoreStore)
    assert isinstance(_tracker_conforms, TrackerStore)
    assert isinstance(_continuity_conforms, ContinuityCheck)


def test_execute_returns_an_analysis_report_carrying_script_findings_and_tracker_items() -> None:
    use_case = _use_case()

    report = use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    assert isinstance(report, AnalysisReport)
    assert report.script.project_id == "proj-1"
    assert report.script.script_id == "scr-1"
    assert len(report.findings) == 1
    assert len(report.tracker_items) == 1


def test_the_reports_script_carries_the_runs_version_gcs_uri_and_jurisdiction() -> None:
    use_case = _use_case()

    report = use_case.execute("proj-1", "scr-1", 3, "gs://bucket/v3.pdf", _MEXICO, _AT)

    assert report.script.version == 3
    assert report.script.gcs_uri == "gs://bucket/v3.pdf"
    assert report.script.jurisdiction_code == _MEXICO.code


def test_extract_is_called_once_with_every_scene() -> None:
    # `extract` batching (CP-007's `_BATCH_SIZE`) belongs to the adapter, not
    # this use case: exactly one call, carrying every scene.
    calls: list[str] = []
    scenes = [_scene(1), _scene(2), _scene(3)]
    use_case = AnalyzeScript(
        ingestion=_Ingestion(scenes),
        extractor=_Extractor([_finding()], log=calls),
        grounding=_Grounding(),
        research=_Research(),
        lore=_LoreStore(),
        tracker=_Tracker(),
        continuity=_Continuity(),
    )

    use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    assert calls.count("extract") == 1


def test_deduped_findings_get_sequential_evt_ids_in_first_appearance_order() -> None:
    quilmes = _finding(finding_id="uuid-a", raw_text="Quilmes", scene_number=1)
    ferrari = _finding(finding_id="uuid-b", raw_text="Ferrari", scene_number=2)
    use_case = _use_case(scenes=[_scene(1), _scene(2)], findings=[quilmes, ferrari])

    report = use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    ids = [finding.finding_id for finding in report.findings]
    assert ids == ["EVT-001", "EVT-002"]
    # The extractor's placeholder UUID (D13) never survives to the report.
    assert "uuid-a" not in ids
    assert "uuid-b" not in ids


def test_the_same_input_yields_the_same_ids_across_two_runs() -> None:
    findings = [_finding(finding_id="uuid-a", raw_text="Quilmes")]
    use_case_a = _use_case(findings=findings)
    use_case_b = _use_case(findings=findings)

    report_a = use_case_a.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)
    report_b = use_case_b.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    assert [f.finding_id for f in report_a.findings] == [f.finding_id for f in report_b.findings]


def test_high_confidence_leaves_risk_and_needs_review_unchanged() -> None:
    finding = _finding(risk_level=RiskLevel.MEDIUM)
    claim = _claim(confidence=Confidence.HIGH)
    use_case = _use_case(findings=[finding], research=_Research(claim=claim))

    report = use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    assert report.findings[0].risk_level == RiskLevel.MEDIUM
    assert report.tracker_items[0].needs_review is False


def test_medium_confidence_raises_risk_one_step() -> None:
    finding = _finding(risk_level=RiskLevel.MEDIUM)
    claim = _claim(confidence=Confidence.MEDIUM)
    use_case = _use_case(findings=[finding], research=_Research(claim=claim))

    report = use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    assert report.findings[0].risk_level == RiskLevel.HIGH
    assert report.tracker_items[0].needs_review is False


def test_low_confidence_sets_needs_review_and_leaves_risk_unchanged() -> None:
    finding = _finding(risk_level=RiskLevel.MEDIUM)
    claim = _claim(confidence=Confidence.LOW)
    use_case = _use_case(findings=[finding], research=_Research(claim=claim))

    report = use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    assert report.findings[0].risk_level == RiskLevel.MEDIUM
    assert report.tracker_items[0].needs_review is True


def test_citations_land_on_the_finding_not_the_tracker_item() -> None:
    citation = Citation(uri="https://law.example/mx", title="Ley Federal", snippet="...")
    grounding = _Grounding(answer=GroundedAnswer(text="grounded text", citations=(citation,)))
    use_case = _use_case(grounding=grounding)

    report = use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    assert report.findings[0].citations == (citation,)


def test_rights_claim_fields_land_on_the_tracker_item_not_the_finding() -> None:
    claim = _claim(
        holder="Cerveceria Quilmes",
        contact="legal@quilmes.example",
        litigation_posture="cease and desist sent 2024",
    )
    use_case = _use_case(research=_Research(claim=claim))

    report = use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    item = report.tracker_items[0]
    assert item.contact == "legal@quilmes.example"
    assert item.litigation_posture == "cease and desist sent 2024"
    # `Finding` carries no holder/contact/litigation_posture fields at all
    # (SDD Section 2) -- nothing to assert their absence on beyond the type.


def test_continuity_findings_skip_the_rights_research_lookup() -> None:
    continuity_finding = Finding(
        finding_id="placeholder-uuid",
        scene_number=1,
        page=1,
        raw_text="The mural was already destroyed in scene 3.",
        category=Category.CONTINUITY,
        ner_label=None,
        risk_level=RiskLevel.MEDIUM,
        required_document="",
        contradicts="F1",
    )
    research = _Research()
    use_case = _use_case(
        findings=[], continuity=_Continuity(finding=continuity_finding), research=research
    )

    report = use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    assert len(report.findings) == 1
    assert report.findings[0].category == Category.CONTINUITY
    assert research.calls == []


def test_continuity_and_policy_findings_skip_the_legal_grounding_lookup() -> None:
    ip_categories = (
        (Category.INDUSTRIAL_PROPERTY, NerLabel.BRAND),
        (Category.COPYRIGHT_WORKS, NerLabel.MUSIC_EXISTING),
        (Category.PERSONALITY_IMAGE, NerLabel.REAL_PERSON),
        (Category.INTEGRATED_VISUAL, NerLabel.MEDIA_AV),
        (Category.LOCATIONS_PERMITS, NerLabel.LOCATION_PUB),
        (Category.SPECIAL_SYMBOLS, NerLabel.SPECIAL_SYMBOL),
    )
    ip_findings = [
        _finding(finding_id=f"uuid-{index}", raw_text="Quilmes", category=category, ner_label=label)
        for index, (category, label) in enumerate(ip_categories)
    ]
    continuity_finding = _finding(
        finding_id="uuid-continuity",
        raw_text="The mural was already destroyed in scene 3.",
        category=Category.CONTINUITY,
        ner_label=None,
        required_document="",
    )
    policy_finding = _finding(
        finding_id="uuid-policy",
        raw_text="A visible cigarette brand violates local policy.",
        category=Category.POLICY,
        ner_label=None,
        required_document="",
    )
    grounding = _Grounding()
    use_case = _use_case(
        findings=[*ip_findings, continuity_finding, policy_finding], grounding=grounding
    )

    use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    assert len(grounding.calls) == 6
    called_queries = {query for query, _ in grounding.calls}
    assert called_queries == {_GROUNDING_TERMS[category] for category, _ in ip_categories}


def test_a_continuity_finding_reaches_the_report_with_no_citations() -> None:
    citation = Citation(uri="https://law.example/mx", title="Ley Federal", snippet="...")
    grounding = _Grounding(answer=GroundedAnswer(text="grounded text", citations=(citation,)))
    continuity_finding = Finding(
        finding_id="placeholder-uuid",
        scene_number=1,
        page=1,
        raw_text="The mural was already destroyed in scene 3.",
        category=Category.CONTINUITY,
        ner_label=None,
        risk_level=RiskLevel.MEDIUM,
        required_document="",
        contradicts="F1",
    )
    use_case = _use_case(
        findings=[], continuity=_Continuity(finding=continuity_finding), grounding=grounding
    )

    report = use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    assert len(report.findings) == 1
    assert report.findings[0].citations == ()


def test_every_scene_is_written_to_the_lore_store() -> None:
    scenes = [_scene(1), _scene(2)]
    lore = _LoreStore()
    use_case = _use_case(scenes=scenes, lore=lore)

    use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    assert len(lore.indexed) == 1
    indexed_project, indexed_records = lore.indexed[0]
    assert indexed_project == "proj-1"
    assert list(indexed_records) == scenes


def test_record_script_is_called_once_with_the_runs_script_after_save() -> None:
    tracker = _Tracker()
    use_case = _use_case(tracker=tracker)

    use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    assert len(tracker.recorded) == 1
    recorded = tracker.recorded[0]
    assert recorded.project_id == "proj-1"
    assert recorded.version == 1
    assert recorded.gcs_uri == "gs://bucket/v1.pdf"


def test_every_finding_becomes_a_blocked_tracker_item_at_version_1_scoped_to_project() -> None:
    use_case = _use_case()

    report = use_case.execute("proj-9", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    item = report.tracker_items[0]
    assert item.state == TrackerState.BLOCKED
    assert item.version == 1
    assert item.project_id == "proj-9"


def test_a_no_grounded_source_leaves_that_finding_without_citations() -> None:
    # `raise_for` matches on the query, and since CP-055 the query is the
    # category's legal terms rather than the script text. The fake also answers
    # with a citation by default, so empty citations can only mean the
    # degradation ran -- otherwise this test passes whether or not it does.
    grounding = _Grounding(
        answer=GroundedAnswer(
            text="grounded",
            citations=(Citation(uri="https://law.example/mx", title="Ley", snippet="..."),),
        ),
        raise_for="trademark",
        error=NoGroundedSource("INDUSTRIAL_PROPERTY"),
    )
    use_case = _use_case(grounding=grounding)

    report = use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    assert grounding.calls, "grounding was never called, so nothing was degraded"
    assert report.findings[0].citations == ()


def test_a_no_rights_holder_found_leaves_that_findings_tracker_item_without_contact() -> None:
    research = _Research(raise_for="Quilmes", error=NoRightsHolderFound("Quilmes"))
    use_case = _use_case(research=research)

    report = use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    assert report.tracker_items[0].contact == ""
    assert report.tracker_items[0].litigation_posture == ""


def test_an_enrichment_failure_on_one_finding_does_not_affect_another() -> None:
    unresolvable = _finding(finding_id="uuid-a", raw_text="Quilmes", scene_number=1)
    resolvable = _finding(finding_id="uuid-b", raw_text="Ferrari", scene_number=2)
    research = _Research(
        claim=_claim(holder="Ferrari S.p.A."),
        raise_for="Quilmes",
        error=NoRightsHolderFound("Quilmes"),
    )
    use_case = _use_case(
        scenes=[_scene(1), _scene(2)], findings=[unresolvable, resolvable], research=research
    )

    report = use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    by_raw_text = {
        finding.raw_text: item for finding, item in zip(report.findings, report.tracker_items)
    }
    assert by_raw_text["Quilmes"].contact == ""
    assert by_raw_text["Ferrari"].contact == "legal@quilmes.example"


def test_a_bug_in_a_port_propagates_instead_of_being_swallowed() -> None:
    research = _Research(raise_for="Quilmes", error=TypeError("boom"))
    use_case = _use_case(research=research)

    with pytest.raises(TypeError):
        use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)


def test_a_source_unavailable_from_research_propagates_instead_of_being_caught() -> None:
    # `SourceUnavailable` does not subclass `EnrichmentMissing` (D23): a
    # Parallel outage must not be swallowed like an ordinary "no holder
    # found" result.
    research = _Research(raise_for="Quilmes", error=SourceUnavailable("Parallel is down"))
    use_case = _use_case(research=research)

    with pytest.raises(SourceUnavailable):
        use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)


def test_a_source_unavailable_from_grounding_propagates_instead_of_being_caught() -> None:
    # Same guarantee on the `LegalGrounding` catch site: an outage there must
    # not degrade into a citation-less finding that looks like a normal
    # clearance outcome.
    grounding = _Grounding(raise_for="trademark", error=SourceUnavailable("Vertex is down"))
    use_case = _use_case(grounding=grounding)

    with pytest.raises(SourceUnavailable):
        use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)


def test_ingestion_parse_raising_propagates_unchanged() -> None:
    use_case = _use_case(ingestion_error=RuntimeError("Document AI is down"))

    with pytest.raises(RuntimeError):
        use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)


def test_findings_naming_the_same_asset_across_scenes_collapse_into_one_tracker_item() -> None:
    first = _finding(finding_id="uuid-a", raw_text="Quilmes", scene_number=1)
    second = _finding(finding_id="uuid-b", raw_text="Quilmes", scene_number=5)
    use_case = _use_case(scenes=[_scene(1), _scene(5)], findings=[first, second])

    report = use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    assert len(report.findings) == 1
    assert report.tracker_items[0].scene_numbers == (1, 5)


def test_pipeline_runs_ports_in_sdd_order() -> None:
    log: list[str] = []
    use_case = AnalyzeScript(
        ingestion=_Ingestion([_scene(1)], log=log),
        extractor=_Extractor([_finding()], log=log),
        grounding=_Grounding(log=log),
        research=_Research(log=log),
        lore=_LoreStore(log=log),
        tracker=_Tracker(log=log),
        continuity=_Continuity(log=log),
    )

    use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    assert log.index("parse") < log.index("extract")
    assert log.index("extract") < log.index("lore.search")
    assert log.index("lore.search") < log.index("continuity.check")
    assert log.index("continuity.check") < log.index("ground")
    assert log.index("ground") < log.index("research")
    assert log.index("research") < log.index("lore.index")
    assert log.index("lore.index") < log.index("tracker.save")
    assert log.index("tracker.save") < log.index("record_script")


class _PositionalOnlyIngestion:
    def __init__(self, scenes: list[Scene]) -> None:
        self._scenes = scenes

    def parse(self, a: str, b: str) -> list[Scene]:
        return list(self._scenes)


class _PositionalOnlyExtractor:
    def __init__(self, findings: list[Finding]) -> None:
        self._findings = findings

    def extract(self, a: list[Scene], b: Jurisdiction) -> list[Finding]:
        return list(self._findings)


class _PositionalOnlyGrounding:
    def ground(self, a: str, b: Jurisdiction) -> GroundedAnswer:
        return GroundedAnswer(text="grounded", citations=())


class _PositionalOnlyResearch:
    def __init__(self, claim: RightsClaim) -> None:
        self._claim = claim

    def find(self, a: str, b: Category, c: Jurisdiction) -> RightsClaim:
        return self._claim


class _PositionalOnlyLoreStore:
    def index(self, a: str, b: list[BibleFact | Scene]) -> None:
        return None

    def search(self, a: str, b: str, c: int) -> list[BibleFact]:
        return []


class _PositionalOnlyTracker:
    def __init__(self) -> None:
        self.saved: list[list[TrackerItem]] = []

    def save(self, a: list[TrackerItem]) -> None:
        self.saved.append(list(a))

    def latest(self, a: str) -> TrackerItem:
        raise KeyError(a)

    def latest_for_project(self, a: str) -> list[TrackerItem]:
        return []

    def record_script(self, a: Script) -> None:
        return None

    def latest_script(self, a: str) -> Script | None:
        return None


class _PositionalOnlyContinuity:
    def check(self, a: Scene, b: list[BibleFact]) -> Finding | None:
        return None


def test_port_methods_are_called_positionally() -> None:
    """D15: a keyword call through any of these seven fakes raises `TypeError`."""
    tracker = _PositionalOnlyTracker()
    use_case = AnalyzeScript(
        ingestion=_PositionalOnlyIngestion([_scene()]),
        extractor=_PositionalOnlyExtractor([_finding()]),
        grounding=_PositionalOnlyGrounding(),
        research=_PositionalOnlyResearch(_claim()),
        lore=_PositionalOnlyLoreStore(),
        tracker=tracker,
        continuity=_PositionalOnlyContinuity(),
    )

    report = use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    assert len(report.findings) == 1
    assert len(tracker.saved) == 1


# --- CP-055 follow-up: the grounding query has to be findable ---------------
#
# `_grounding_query` built `f"{category.value} clearance: {raw_text}"`, so the
# Ferrari finding searched for "INDUSTRIAL_PROPERTY clearance: a Ferrari
# Testarossa". No statute contains an enum name, the word "clearance", or a car
# model. Probed against the real data store on 2026-09-03: that shape retrieves
# zero documents, and adding the asset name to a query that does work drops it
# from two hits to one.
#
# SDD section 4.1 step 5 always said grounding asks what the law says about
# "this category of use". The asset name was never meant to be in the query;
# the asset is what RightsResearch looks up, not what the statute is about.


def test_the_grounding_query_never_contains_the_script_text() -> None:
    """The bug, stated as a property.

    A statute is about a category of use. Putting the quoted script fragment in
    the query only adds terms no legal text contains.
    """
    grounding = _Grounding()
    finding = _finding(raw_text="a Ferrari Testarossa", category=Category.INDUSTRIAL_PROPERTY)
    use_case = _use_case(findings=[finding], grounding=grounding)

    use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    query, _ = grounding.calls[0]
    assert "Ferrari" not in query
    assert "Testarossa" not in query


def test_the_grounding_query_names_the_legal_subject_not_the_enum() -> None:
    grounding = _Grounding()
    finding = _finding(raw_text="a Ferrari Testarossa", category=Category.INDUSTRIAL_PROPERTY)
    use_case = _use_case(findings=[finding], grounding=grounding)

    use_case.execute("proj-1", "scr-1", 1, "gs://bucket/v1.pdf", _MEXICO, _AT)

    query, _ = grounding.calls[0]
    assert "INDUSTRIAL_PROPERTY" not in query
    assert "trademark" in query


def test_every_category_that_grounds_has_search_terms() -> None:
    """No category reaches the store with an empty or enum-shaped query.

    CONTINUITY and POLICY never ground at all, so they are excluded here rather
    than given terms they would not use.
    """
    for category in Category:
        if category in _NO_LOOKUP_CATEGORIES:
            continue
        terms = _GROUNDING_TERMS[category]
        assert terms.strip()
        assert category.value not in terms
