"""Runs the full clearance pipeline over one screenplay (docs/plan/sdd.md
Section 4.1, Section 3).

The ordered flow SDD Section 4.1 describes: parse the script into scenes,
extract raw findings once over every scene, run the per-scene continuity
check against the bible, dedupe the combined findings by asset (CP-019), then
for each deduped finding ground it in the jurisdiction's law and research its
rights holder -- skipping both lookups for a CONTINUITY or POLICY finding,
which names a bible contradiction rather than an asset with a rights holder
or a legal question to resolve (Decision D32). The confidence-to-risk rule is
CP-021's `resolve_risk`, not reimplemented here. Every scene is written to
the LoreStore and every finding becomes a BLOCKED tracker item at
`version = 1`, scoped to the run's `project_id` (CHECKPOINTS.md Decision
D24). The run's `Script` is recorded to `TrackerStore.latest_script` after
`tracker.save`, so `EvaluateDelta` has a previous version to diff against
(CHECKPOINTS.md Decision D30).

`finding_id` is minted here as `EVT-NNN`, sequential in first-appearance
order, discarding the extractor's placeholder UUID: an adapter cannot know a
project's existing sequence, and a UUID is not stable across script versions,
which is the identity `EvaluateDelta`'s carry-forward join needs
(CHECKPOINTS.md Decision D13).

Only `EnrichmentMissing` (`clearcut.domain.errors`) is caught, by name, never
a bare `Exception` (Decision D23): `NoGroundedSource` and `NoRightsHolderFound`
each subclass it, so one unresolvable rights holder or one ungrounded
citation degrades that single finding rather than failing a 200-scene
analysis. `SourceUnavailable` and any other exception a port raises --
including a bug like a stray `TypeError` -- propagate unchanged, the same way
`ingestion.parse` raising propagates unchanged: a partial report from a
script that never parsed would be a lie.
"""

from dataclasses import dataclass, replace

from clearcut.application.ports import (
    ContinuityCheck,
    LegalGrounding,
    LoreStore,
    RightsClaim,
    RightsResearch,
    SceneExtractor,
    ScriptIngestion,
    TrackerStore,
)
from clearcut.application.risk_rules import resolve_risk
from clearcut.domain.bible import BibleFact
from clearcut.domain.dedupe import dedupe_findings
from clearcut.domain.errors import EnrichmentMissing
from clearcut.domain.finding import Category, Citation, Finding, RiskLevel
from clearcut.domain.jurisdiction import Jurisdiction
from clearcut.domain.script import Scene, Script
from clearcut.domain.tracker import TrackerItem, TrackerState

# How many bible facts to retrieve per scene for the continuity check. Never
# varied, so it is a constant, not constructor config (AGENT.md Section 4).
_LORE_SEARCH_LIMIT = 5

# A CONTINUITY or POLICY finding names a bible contradiction, not an asset
# with a rights holder or a legal question (D11, D32, SDD Section 4.1 step 5).
_NO_LOOKUP_CATEGORIES = frozenset({Category.CONTINUITY, Category.POLICY})

_DedupedFinding = tuple[Finding, tuple[int, ...]]


@dataclass(frozen=True)
class AnalysisReport:
    """The full result of one `AnalyzeScript` run (SDD Section 4.1 step 8)."""

    script: Script
    findings: tuple[Finding, ...]
    tracker_items: tuple[TrackerItem, ...]


def _grounding_query(finding: Finding) -> str:
    return f"{finding.category.value} clearance: {finding.raw_text}"


def _resolve(finding: Finding, claim: RightsClaim | None) -> tuple[RiskLevel, bool]:
    """The confidence-to-risk rule (CP-021), applied only when research ran."""
    if claim is None:
        return finding.risk_level, False
    decision = resolve_risk(finding, claim)
    return decision.risk_level, decision.needs_review


def _tracker_item(
    finding: Finding,
    project_id: str,
    scene_numbers: tuple[int, ...],
    claim: RightsClaim | None,
    needs_review: bool,
    at: str,
) -> TrackerItem:
    """`RightsResearch`'s holder-facing fields land here, never on the finding
    (SDD Section 2)."""
    return TrackerItem(
        item_id=finding.finding_id,
        project_id=project_id,
        finding_id=finding.finding_id,
        scene_numbers=scene_numbers,
        state=TrackerState.BLOCKED,
        required_document=finding.required_document,
        contact=claim.contact if claim is not None else "",
        litigation_posture=claim.litigation_posture if claim is not None else "",
        note="",
        updated_at=at,
        version=1,
        needs_review=needs_review,
    )


class AnalyzeScript:
    """`AnalyzeScript(ingestion, extractor, grounding, research, lore, tracker,
    continuity)` (SDD Section 3, D11)."""

    def __init__(
        self,
        ingestion: ScriptIngestion,
        extractor: SceneExtractor,
        grounding: LegalGrounding,
        research: RightsResearch,
        lore: LoreStore,
        tracker: TrackerStore,
        continuity: ContinuityCheck,
    ) -> None:
        self._ingestion = ingestion
        self._extractor = extractor
        self._grounding = grounding
        self._research = research
        self._lore = lore
        self._tracker = tracker
        self._continuity = continuity

    def execute(
        self,
        project_id: str,
        script_id: str,
        version: int,
        gcs_uri: str,
        jurisdiction: Jurisdiction,
        at: str,
    ) -> AnalysisReport:
        scenes = self._ingestion.parse(gcs_uri, script_id)
        script = Script(
            script_id=script_id,
            project_id=project_id,
            version=version,
            gcs_uri=gcs_uri,
            jurisdiction_code=jurisdiction.code,
            scenes=scenes,
        )
        extracted = self._extractor.extract(scenes, jurisdiction)
        contradictions = self._continuity_findings(project_id, scenes)
        deduped = dedupe_findings(extracted + contradictions)
        findings, items = self._enrich(deduped, project_id, jurisdiction, at)

        records: list[BibleFact | Scene] = list(scenes)
        self._lore.index(project_id, records)
        self._tracker.save(items)
        self._tracker.record_script(script)

        return AnalysisReport(script=script, findings=tuple(findings), tracker_items=tuple(items))

    def _continuity_findings(self, project_id: str, scenes: list[Scene]) -> list[Finding]:
        """One `ContinuityCheck` call per scene, against that scene's nearest
        bible facts (SDD Section 4.1 step 5)."""
        findings: list[Finding] = []
        for scene in scenes:
            facts = self._lore.search(project_id, scene.text, _LORE_SEARCH_LIMIT)
            finding = self._continuity.check(scene, facts)
            if finding is not None:
                findings.append(finding)
        return findings

    def _enrich(
        self,
        deduped: list[_DedupedFinding],
        project_id: str,
        jurisdiction: Jurisdiction,
        at: str,
    ) -> tuple[list[Finding], list[TrackerItem]]:
        findings: list[Finding] = []
        items: list[TrackerItem] = []
        for index, (finding, scene_numbers) in enumerate(deduped, start=1):
            finding_id = f"EVT-{index:03d}"
            citations = self._citations_for(finding, jurisdiction)
            claim = self._claim_for(finding, jurisdiction)
            risk_level, needs_review = _resolve(finding, claim)
            resolved = replace(
                finding, finding_id=finding_id, citations=citations, risk_level=risk_level
            )
            findings.append(resolved)
            items.append(
                _tracker_item(resolved, project_id, scene_numbers, claim, needs_review, at)
            )
        return findings, items

    def _citations_for(self, finding: Finding, jurisdiction: Jurisdiction) -> tuple[Citation, ...]:
        if finding.category in _NO_LOOKUP_CATEGORIES:
            return ()
        try:
            grounded = self._grounding.ground(_grounding_query(finding), jurisdiction)
        except EnrichmentMissing:
            # `NoGroundedSource` (adapters/gcp/vertex_search.py) subclasses
            # `EnrichmentMissing` (D23) -- an unlicensed source for one
            # finding does not fail the whole analysis.
            return ()
        return grounded.citations

    def _claim_for(self, finding: Finding, jurisdiction: Jurisdiction) -> RightsClaim | None:
        if finding.category in _NO_LOOKUP_CATEGORIES:
            return None
        try:
            return self._research.find(finding.raw_text, finding.category, jurisdiction)
        except EnrichmentMissing:
            # `NoRightsHolderFound` (adapters/parallel/research.py) subclasses
            # `EnrichmentMissing` (D23) -- an uncited claim is a normal
            # clearance outcome, not an outage.
            return None
