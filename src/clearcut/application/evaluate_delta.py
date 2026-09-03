"""Re-analyzes only what changed between two script versions (docs/plan/sdd.md
Section 4.3; ADR 0007; CHECKPOINTS.md Decisions D19, D30, D37).

Triggered when a project that already has a stored script version uploads
another one. After parse and hash, `diff_scenes` (CP-020) joins the new
scenes against `tracker.latest_script(project_id)`'s scenes on `(number,
heading)`:

- UNCHANGED scenes are never re-extracted, re-enriched, or re-embedded --
  their findings and tracker items carry forward exactly as they are.
- ADDED and CHANGED scenes are re-extracted, re-continuity-checked,
  re-grounded, and re-researched -- the same enrichment `AnalyzeScript` runs,
  scoped to this smaller set.
- REMOVED scenes keep their open tracker items: nothing is deleted, because a
  cut scene can return in a later version. Each gets a note recording why,
  through `TrackerItem.noted` (CP-028) so the versioned-row rule (D22) stays
  owned by `TrackerItem`, not by this module.
- Carry-forward matches by scene overlap (D37): a re-extracted finding on a
  CHANGED scene takes over the `finding_id` and tracker state of an existing
  item whose `scene_numbers` overlap the CHANGED set. `dedupe_findings`
  (CP-019) runs first, so an asset mentioned in both a CHANGED and a newly
  ADDED scene in the same upload collapses to one item before this lookup
  runs. A CHANGED scene whose matched item was CLEARED keeps CLEARED, gets
  `needs_review` set through `TrackerItem.flagged_for_review`, and triggers
  exactly one `Notifier.notify` (ADR 0007). A genuinely new asset mints a
  fresh `EVT-NNN` id, continuing the project's existing sequence, and starts
  BLOCKED.

**Known limitation (D37).** The join above is by scene, not by asset, because
no port persists a `Finding`'s `raw_text`/`category` once a use case returns
(no findings table -- see CHECKPOINTS.md Backlog) -- there is nothing to join
an existing item against except the scene it sits on. An asset that moves to
a different scene between versions therefore does not carry its clearance:
the re-extracted finding on its new scene finds no candidate item there and
mints a fresh `EVT-NNN` id at BLOCKED, while the existing item tied to its
old scene finds no re-extracted finding that matches, so it stays open, gets
flagged for review, and carries a note naming the scene it was cleared
against (`TrackerItem.flagged_and_noted`). A human clears the asset a second
time. Recovering the original clearance needs a stored asset identity -- a
category and a normalized text on `TrackerItem`, the columns behind them, and
a `TrackerStore` read that joins on the pair -- which is recorded in the
Backlog with its cost, not built here.

`record_script` is called for the version this run produces, after the
tracker write, so a v3 upload has a v2 to diff against (D30).
"""

import re
from dataclasses import replace

from clearcut.application.analyze_script import AnalysisReport
from clearcut.application.grounding_query import grounding_query
from clearcut.application.ports import (
    ContinuityCheck,
    LegalGrounding,
    LoreStore,
    Notifier,
    RightsClaim,
    RightsResearch,
    SceneExtractor,
    ScriptIngestion,
    TrackerStore,
)
from clearcut.application.risk_rules import resolve_risk
from clearcut.domain.dedupe import dedupe_findings
from clearcut.domain.delta import DeltaKind, SceneDelta, diff_scenes
from clearcut.domain.errors import EnrichmentMissing, RecordNotFound
from clearcut.domain.finding import Category, Citation, Finding, RiskLevel
from clearcut.domain.jurisdiction import Jurisdiction
from clearcut.domain.script import Scene, Script
from clearcut.domain.tracker import TrackerItem, TrackerState

# How many bible facts to retrieve per scene for the continuity check --
# mirrors `AnalyzeScript`'s constant, never varied (AGENT.md Section 4).
_LORE_SEARCH_LIMIT = 5

_NO_LOOKUP_CATEGORIES = frozenset({Category.CONTINUITY, Category.POLICY})

_EVT_PATTERN = re.compile(r"^EVT-(\d+)$")

_DedupedFinding = tuple[Finding, tuple[int, ...]]


class NoPreviousScriptVersion(RecordNotFound):
    """Raised when a project has no stored script version to diff against.

    Subclasses `RecordNotFound` (D30) so CP-029's existing 404 mapping covers
    it without a fourth error class.
    """

    def __init__(self, project_id: str) -> None:
        super().__init__(
            f"no previous script version for project_id={project_id!r}; run AnalyzeScript first"
        )


def _next_evt_number(items: list[TrackerItem]) -> int:
    numbers = [
        int(match.group(1))
        for item in items
        if (match := _EVT_PATTERN.match(item.finding_id)) is not None
    ]
    return max(numbers, default=0) + 1


def _scene_numbers_by_kind(deltas: list[SceneDelta]) -> tuple[set[int], set[int], set[int]]:
    added = {d.scene_number for d in deltas if d.kind is DeltaKind.ADDED}
    changed = {d.scene_number for d in deltas if d.kind is DeltaKind.CHANGED}
    removed = {d.scene_number for d in deltas if d.kind is DeltaKind.REMOVED}
    return added, changed, removed


def _is_all_within(item: TrackerItem, numbers: set[int]) -> bool:
    return set(item.scene_numbers) <= numbers


def _overlaps(item: TrackerItem, numbers: set[int]) -> bool:
    return bool(set(item.scene_numbers) & numbers)


def _removed_note(item: TrackerItem, version: int) -> str:
    scenes = ", ".join(str(number) for number in sorted(item.scene_numbers))
    return f"scene {scenes} removed in version {version}"


def _stale_note(item: TrackerItem, version: int) -> str:
    """Names the scene(s) `item` was cleared against, so a producer reading a
    flagged CLEARED row learns why -- rather than a bare flag over an empty
    note (D37)."""
    scenes = ", ".join(str(number) for number in sorted(item.scene_numbers))
    return f"cleared against scene {scenes}; no matching finding there in version {version}"


def _partition_existing(
    existing_items: list[TrackerItem], changed: set[int], removed: set[int]
) -> tuple[list[TrackerItem], list[TrackerItem]]:
    """Existing items tied to a CHANGED scene (candidates for scene-overlap
    matching) versus everything else that is not all-REMOVED (carried
    forward untouched)."""
    candidates = [item for item in existing_items if _overlaps(item, changed)]
    carried = [
        item
        for item in existing_items
        if not _overlaps(item, changed) and not _is_all_within(item, removed)
    ]
    return candidates, carried


class EvaluateDelta:
    """`EvaluateDelta(ingestion, extractor, grounding, research, lore,
    tracker, continuity, notifier)` (SDD Section 4.3, ADR 0007, D30)."""

    def __init__(
        self,
        ingestion: ScriptIngestion,
        extractor: SceneExtractor,
        grounding: LegalGrounding,
        research: RightsResearch,
        lore: LoreStore,
        tracker: TrackerStore,
        continuity: ContinuityCheck,
        notifier: Notifier,
    ) -> None:
        self._ingestion = ingestion
        self._extractor = extractor
        self._grounding = grounding
        self._research = research
        self._lore = lore
        self._tracker = tracker
        self._continuity = continuity
        self._notifier = notifier

    def execute(
        self,
        project_id: str,
        script_id: str,
        version: int,
        gcs_uri: str,
        jurisdiction: Jurisdiction,
        at: str,
    ) -> AnalysisReport:
        previous = self._tracker.latest_script(project_id)
        if previous is None:
            raise NoPreviousScriptVersion(project_id)

        scenes = self._ingestion.parse(gcs_uri, script_id)
        script = Script(
            script_id=script_id,
            project_id=project_id,
            version=version,
            gcs_uri=gcs_uri,
            jurisdiction_code=jurisdiction.code,
            scenes=scenes,
        )

        added, changed, removed = _scene_numbers_by_kind(diff_scenes(previous.scenes, scenes))
        reextract_scenes = [scene for scene in scenes if scene.number in added | changed]

        existing_items = self._tracker.latest_for_project(project_id)
        candidates, carried_items = _partition_existing(existing_items, changed, removed)
        deduped = self._extract_and_dedupe(project_id, reextract_scenes, jurisdiction)

        findings, saved_items, passthrough_items, unmatched = self._resolve_deduped(
            deduped, project_id, jurisdiction, at, candidates, existing_items
        )
        leftover_items = [self._carry_forward_leftover(item, version, at) for item in unmatched]
        removed_items = [
            item.noted(_removed_note(item, version), at)
            for item in existing_items
            if _is_all_within(item, removed)
        ]

        self._lore.index(project_id, list(reextract_scenes))
        self._save_and_record(saved_items + leftover_items + removed_items, script)

        all_items = tuple(
            carried_items + passthrough_items + saved_items + leftover_items + removed_items
        )
        return AnalysisReport(script=script, findings=tuple(findings), tracker_items=all_items)

    def _extract_and_dedupe(
        self, project_id: str, scenes: list[Scene], jurisdiction: Jurisdiction
    ) -> list[_DedupedFinding]:
        extracted = self._extractor.extract(scenes, jurisdiction)
        contradictions = self._continuity_findings(project_id, scenes)
        return dedupe_findings(extracted + contradictions)

    def _save_and_record(self, to_save: list[TrackerItem], script: Script) -> None:
        if to_save:
            self._tracker.save(to_save)
        self._tracker.record_script(script)

    def _carry_forward_leftover(self, item: TrackerItem, version: int, at: str) -> TrackerItem:
        """An existing item tied to a CHANGED scene that no re-extracted
        finding matched -- the asset it named is no longer detected there.

        Kept open either way (never dropped): a CLEARED item gets the same
        flag-and-notify treatment a matched CLEARED item gets (ADR 0007); any
        other state gets a note recording that its scene changed.
        """
        if item.state is TrackerState.CLEARED:
            return self._flag_note_and_notify(item, version, at)
        return item.noted(f"scene {item.scene_numbers} changed in version {version}", at)

    def _flag_and_notify(self, item: TrackerItem, at: str) -> TrackerItem:
        updated = item.flagged_for_review(at)
        self._notifier.notify(updated, "scene changed after clearance; needs re-review")
        return updated

    def _flag_note_and_notify(self, item: TrackerItem, version: int, at: str) -> TrackerItem:
        """The CLEARED item this run could not match to anything: flagged and
        noted in the one tracker write `TrackerItem.flagged_and_noted`
        performs, so it costs one version bump, not two (D37)."""
        updated = item.flagged_and_noted(_stale_note(item, version), at)
        self._notifier.notify(updated, "scene changed after clearance; needs re-review")
        return updated

    def _continuity_findings(self, project_id: str, scenes: list[Scene]) -> list[Finding]:
        findings: list[Finding] = []
        for scene in scenes:
            facts = self._lore.search(project_id, scene.text, _LORE_SEARCH_LIMIT)
            finding = self._continuity.check(scene, facts)
            if finding is not None:
                findings.append(finding)
        return findings

    def _resolve_deduped(
        self,
        deduped: list[_DedupedFinding],
        project_id: str,
        jurisdiction: Jurisdiction,
        at: str,
        candidates: list[TrackerItem],
        existing_items: list[TrackerItem],
    ) -> tuple[list[Finding], list[TrackerItem], list[TrackerItem], list[TrackerItem]]:
        findings: list[Finding] = []
        saved_items: list[TrackerItem] = []
        passthrough_items: list[TrackerItem] = []
        remaining = list(candidates)
        next_number = _next_evt_number(existing_items)

        for finding, scene_numbers in deduped:
            citations = self._citations_for(finding, jurisdiction)
            claim = self._claim_for(finding, jurisdiction)
            risk_level, needs_review = _resolve(finding, claim)
            match = _pop_match(remaining, scene_numbers)

            if match is not None:
                resolved, item, is_saved = self._match_outcome(
                    finding, citations, risk_level, match, at
                )
                findings.append(resolved)
                (saved_items if is_saved else passthrough_items).append(item)
                continue

            resolved, item = _mint_outcome(
                finding,
                citations,
                risk_level,
                needs_review,
                claim,
                project_id,
                scene_numbers,
                at,
                next_number,
            )
            next_number += 1
            findings.append(resolved)
            saved_items.append(item)

        return findings, saved_items, passthrough_items, remaining

    def _match_outcome(
        self,
        finding: Finding,
        citations: tuple[Citation, ...],
        risk_level: RiskLevel,
        match: TrackerItem,
        at: str,
    ) -> tuple[Finding, TrackerItem, bool]:
        """The re-extracted finding adopts `match`'s identity (D13-style
        stability); a CLEARED match is flagged and notified, anything else
        carries forward untouched."""
        resolved = replace(
            finding, finding_id=match.finding_id, citations=citations, risk_level=risk_level
        )
        if match.state is TrackerState.CLEARED:
            return resolved, self._flag_and_notify(match, at), True
        return resolved, match, False

    def _citations_for(self, finding: Finding, jurisdiction: Jurisdiction) -> tuple[Citation, ...]:
        if finding.category in _NO_LOOKUP_CATEGORIES:
            return ()
        query = grounding_query(finding)
        try:
            grounded = self._grounding.ground(query, jurisdiction)
        except EnrichmentMissing:
            # Same D23 boundary AnalyzeScript uses: an unlicensed source for
            # one finding does not fail the whole re-analysis.
            return ()
        return grounded.citations

    def _claim_for(self, finding: Finding, jurisdiction: Jurisdiction) -> RightsClaim | None:
        if finding.category in _NO_LOOKUP_CATEGORIES:
            return None
        try:
            return self._research.find(finding.raw_text, finding.category, jurisdiction)
        except EnrichmentMissing:
            # An uncited claim is a normal clearance outcome, not an outage
            # (D23, same as AnalyzeScript's catch site).
            return None


def _resolve(finding: Finding, claim: RightsClaim | None) -> tuple[RiskLevel, bool]:
    if claim is None:
        return finding.risk_level, False
    decision = resolve_risk(finding, claim)
    return decision.risk_level, decision.needs_review


def _pop_match(remaining: list[TrackerItem], scene_numbers: tuple[int, ...]) -> TrackerItem | None:
    scene_set = set(scene_numbers)
    for index, candidate in enumerate(remaining):
        if set(candidate.scene_numbers) & scene_set:
            return remaining.pop(index)
    return None


def _mint_outcome(
    finding: Finding,
    citations: tuple[Citation, ...],
    risk_level: RiskLevel,
    needs_review: bool,
    claim: RightsClaim | None,
    project_id: str,
    scene_numbers: tuple[int, ...],
    at: str,
    number: int,
) -> tuple[Finding, TrackerItem]:
    """A genuinely new asset: fresh `EVT-NNN` id, fresh BLOCKED item."""
    resolved = replace(
        finding, finding_id=f"EVT-{number:03d}", citations=citations, risk_level=risk_level
    )
    item = _new_tracker_item(resolved, project_id, scene_numbers, claim, needs_review, at)
    return resolved, item


def _new_tracker_item(
    finding: Finding,
    project_id: str,
    scene_numbers: tuple[int, ...],
    claim: RightsClaim | None,
    needs_review: bool,
    at: str,
) -> TrackerItem:
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
