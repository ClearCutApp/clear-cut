"""Unit tests for the CP-043 demo seed and its eight in-memory adapters
(D36, docs/plan/sdd.md Section 8(d)).

The headline assertion is driven through the real `AnalyzeScript` use case
rather than by reading `scenario.py` back: a seed that can only be verified
by inspecting its own literals is decorated, not seeded.
"""

import ast
import inspect
from types import ModuleType

import pytest

from clearcut.adapters.demo import in_memory, scenario
from clearcut.adapters.demo.in_memory import (
    InMemoryContinuityCheck,
    InMemoryFindingStore,
    InMemoryLegalGrounding,
    InMemoryLoreStore,
    InMemoryNotifier,
    InMemoryRightsResearch,
    InMemorySceneExtractor,
    InMemoryScriptIngestion,
    InMemoryTrackerStore,
)
from clearcut.application.analyze_script import AnalysisReport, AnalyzeScript
from clearcut.application.list_tracker_items import ListTrackerItems
from clearcut.application.ports import (
    ContinuityCheck,
    LegalGrounding,
    LoreStore,
    Notifier,
    RightsResearch,
    SceneExtractor,
    ScriptIngestion,
    TrackerStore,
)
from clearcut.application.resolve_finding import Notify, ResolveFinding, Transition
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.finding import Category, NerLabel
from clearcut.domain.tracker import TrackerState

_AT = "2026-08-31T00:00:00Z"

# Each class bound to its port by an annotated assignment (CP-012, D3),
# written before any `isinstance` narrowing -- the inert-binding pitfall D3
# documents, where narrowing first makes the assignment prove nothing.
_ingestion: ScriptIngestion = InMemoryScriptIngestion()
_extractor: SceneExtractor = InMemorySceneExtractor()
_grounding: LegalGrounding = InMemoryLegalGrounding()
_research: RightsResearch = InMemoryRightsResearch()
_continuity: ContinuityCheck = InMemoryContinuityCheck()
_lore: LoreStore = InMemoryLoreStore()
_tracker: TrackerStore = InMemoryTrackerStore()
_notifier: Notifier = InMemoryNotifier()


def test_each_demo_class_satisfies_its_port() -> None:
    assert isinstance(_ingestion, ScriptIngestion)
    assert isinstance(_extractor, SceneExtractor)
    assert isinstance(_grounding, LegalGrounding)
    assert isinstance(_research, RightsResearch)
    assert isinstance(_continuity, ContinuityCheck)
    assert isinstance(_lore, LoreStore)
    assert isinstance(_tracker, TrackerStore)
    assert isinstance(_notifier, Notifier)


def _use_case(tracker: InMemoryTrackerStore | None = None) -> AnalyzeScript:
    return AnalyzeScript(
        ingestion=InMemoryScriptIngestion(),
        extractor=InMemorySceneExtractor(),
        grounding=InMemoryLegalGrounding(),
        research=InMemoryRightsResearch(),
        lore=InMemoryLoreStore(),
        tracker=tracker if tracker is not None else InMemoryTrackerStore(),
        continuity=InMemoryContinuityCheck(),
        findings=InMemoryFindingStore(),
    )


def _analyze(use_case: AnalyzeScript) -> AnalysisReport:
    return use_case.execute(
        scenario.PROJECT_ID, scenario.SCRIPT_ID, 1, scenario.GCS_URI, scenario.JURISDICTION, _AT
    )


def test_analyze_script_over_the_seed_surfaces_all_three_sdd_8d_findings() -> None:
    report = _analyze(_use_case())

    by_category = {finding.category: finding for finding in report.findings}
    assert set(by_category) == {
        Category.INDUSTRIAL_PROPERTY,
        Category.COPYRIGHT_WORKS,
        Category.CONTINUITY,
    }

    # The asset and NER label per finding, not just the category (BLOCKING 1,
    # CP-043 review 2026-08-31): a suite that never reads `raw_text` or
    # `ner_label` cannot tell the Ferrari from a Lamborghini.
    ferrari = by_category[Category.INDUSTRIAL_PROPERTY]
    assert ferrari.raw_text == "Ferrari Testarossa"
    assert ferrari.ner_label == NerLabel.BRAND

    hotel_california = by_category[Category.COPYRIGHT_WORKS]
    assert hotel_california.raw_text == "Hotel California"
    assert hotel_california.ner_label == NerLabel.MUSIC_EXISTING

    # The contradiction names a fact the seed actually planted (BLOCKING 2,
    # same review): `contradicts` must resolve into `scenario.BIBLE_FACTS`,
    # not merely be non-empty.
    continuity = by_category[Category.CONTINUITY]
    seeded_fact_ids = {fact.fact_id for fact in scenario.BIBLE_FACTS}
    assert continuity.contradicts is not None
    assert continuity.contradicts in seeded_fact_ids


def test_each_finding_carries_the_page_number_its_scene_declares() -> None:
    report = _analyze(_use_case())

    pages_by_scene = {scene.number: scene.page_start for scene in report.script.scenes}
    assert pages_by_scene  # the run actually parsed scenes
    for finding in report.findings:
        assert finding.page == pages_by_scene[finding.scene_number]

    by_category = {finding.category: finding for finding in report.findings}
    assert by_category[Category.INDUSTRIAL_PROPERTY].page == 3
    assert by_category[Category.COPYRIGHT_WORKS].page == 5
    assert by_category[Category.CONTINUITY].page == 8


def test_the_tracker_reads_exactly_three_items_all_blocked() -> None:
    report = _analyze(_use_case())

    assert len(report.tracker_items) == 3
    assert all(item.state == TrackerState.BLOCKED for item in report.tracker_items)


def test_the_two_ip_findings_carry_distinct_rights_holder_contacts() -> None:
    report = _analyze(_use_case())

    contacts = {item.contact for item in report.tracker_items if item.contact}
    assert len(contacts) == 2


def test_a_transition_written_through_save_survives_a_read_through_list_tracker_items() -> None:
    tracker = InMemoryTrackerStore()
    report = _analyze(_use_case(tracker))
    item_id = report.tracker_items[0].item_id
    resolve = ResolveFinding(tracker, InMemoryNotifier())

    resolve.execute(scenario.PROJECT_ID, item_id, Transition(TrackerState.IN_PROGRESS), _AT)

    items = ListTrackerItems(tracker).execute(scenario.PROJECT_ID)
    moved = next(item for item in items if item.item_id == item_id)
    assert moved.state == TrackerState.IN_PROGRESS


def test_notify_records_the_call_in_memory_instead_of_reaching_a_webhook() -> None:
    tracker = InMemoryTrackerStore()
    notifier = InMemoryNotifier()
    report = _analyze(_use_case(tracker))
    item_id = report.tracker_items[0].item_id
    resolve = ResolveFinding(tracker, notifier)

    resolve.execute(
        scenario.PROJECT_ID, item_id, Notify(reason="producer requested an update"), _AT
    )

    assert len(notifier.notifications) == 1
    notified_item, reason = notifier.notifications[0]
    assert notified_item.item_id == item_id
    assert reason == "producer requested an update"


def test_latest_script_returns_the_seeded_version_1_for_the_demo_project() -> None:
    tracker = InMemoryTrackerStore()

    script = tracker.latest_script(scenario.PROJECT_ID)

    assert script is not None
    assert script.version == 1
    assert script.project_id == scenario.PROJECT_ID


def test_latest_script_returns_none_for_every_other_project() -> None:
    tracker = InMemoryTrackerStore()

    assert tracker.latest_script("some-other-project") is None


def test_latest_for_an_unknown_item_id_raises_record_not_found() -> None:
    tracker = InMemoryTrackerStore()

    with pytest.raises(RecordNotFound):
        tracker.latest(scenario.PROJECT_ID, "no-such-item")


def test_search_on_an_unindexed_project_returns_no_facts() -> None:
    lore = InMemoryLoreStore()

    assert lore.search("never-indexed-project", "anything", 5) == []


# Banned per module, not as one shared set (CP-031 review, BLOCKING 3): only
# `in_memory.py`'s five stage spans need `time.perf_counter()` to measure
# their own wall-clock duration for `clearcut_stage_latency_ms`, the same
# metric the live adapters record (ADR 0008, SDD Section 6) -- a real
# duration, not planted data, and `perf_counter()` reads no date. `scenario.py`
# is the planted-data module whose determinism this guard exists to prove, so
# `time` (which also carries `strftime`/`localtime`, wall-clock date reads)
# stays banned there. `datetime` stays banned in both: nothing here needs the
# current date.
_BANNED_IMPORTS_BY_MODULE = {
    scenario: frozenset({"os", "socket", "time", "datetime", "pathlib"}),
    in_memory: frozenset({"os", "socket", "datetime", "pathlib"}),
}


def _imported_root_names(module: ModuleType) -> set[str]:
    tree = ast.parse(inspect.getsource(module))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_neither_demo_module_imports_the_clock_environment_or_a_socket() -> None:
    for module, banned in _BANNED_IMPORTS_BY_MODULE.items():
        assert not _imported_root_names(module) & banned
