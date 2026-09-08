"""In-memory adapters over the CP-043 seed, wired in for `CLEARCUT_MODE=mock`
(D36).

Each class below implements one of the fourteen application ports directly
over `scenario.py`'s planted data -- no service behind them, no I/O, no clock,
no environment read. The stores carry mutable state (an in-process dict or
list), because a producer's PATCH request, `EvaluateDelta`'s carry-forward
join and a script read after an analysis all need a store that remembers a
write, not a canned response; the six read-only adapters echo `scenario.py`'s
data back unconditionally -- the same shape `tests/unit/fakes.py` already
established.

The six stores are not a second implementation of the ClickHouse ones: they
answer the same questions with the same error types, so a route cannot behave
differently by mode. Where two live stores share a table -- `script_versions`,
written through `TrackerStore.record_script` and read through `ScriptStore` --
the two classes here share one list, for the same reason.

This package is production code for the demo image, not a test double:
`composition.py` cannot import from `tests/`, so these classes are what
`CLEARCUT_MODE=mock` actually wires (D36).

No exception class of its own: the two failure paths below (`latest` on an
unknown id, `search` on an unindexed project) raise or return the same way
the live adapters' ports already promise, using the three
`clearcut.domain.errors` types directly. CP-038's contract walk scans every
module under `adapters/` for an unclassified `Exception` subclass, so a new
name here would cost a domain-error decision this checkpoint does not need
to take.
"""

import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict
from threading import RLock
from typing import Any

from opentelemetry import metrics, trace

from clearcut.adapters.demo import scenario
from clearcut.application.ports import GroundedAnswer, RightsClaim
from clearcut.domain.analysis import AnalysisJob
from clearcut.domain.bible import BibleFact
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.finding import Category, Finding
from clearcut.domain.jurisdiction import Jurisdiction
from clearcut.domain.project import Project
from clearcut.domain.script import Scene, Script
from clearcut.domain.tracker import (
    ClearanceSummary,
    TrackerConflict,
    TrackerItem,
    clearance_summary,
)
from clearcut.observability import stage_span

# The bucket `scenario.GCS_URI` already names. Mock mode writes nowhere,
# so this is the shape of a URI rather than a real location.
_DEMO_BUCKET = "clearcut-demo"


# CP-031 (ADR 0008, SDD Section 6): the same five pipeline-stage spans and
# `clearcut_stage_latency_ms` / `clearcut_tracker_items` instruments the live
# adapters record, so a Grafana trace of a mocked demo run (D36) looks like
# any other run. `clearcut_gemini_tokens_total` is deliberately absent here:
# no model runs in mock mode, so nothing is recorded for it.
#
# `trace.get_tracer(__name__)` and `metrics.get_meter(__name__)` are looked
# up fresh inside each helper below rather than cached at import time: a
# module-level `ProxyTracer`/`ProxyMeter` resolved before `composition.py`
# installs the real providers caches that first resolution permanently, so a
# later provider (a fresh one per test, or in principle a re-configured one
# in-process) would never be seen again.
def _tracer() -> trace.Tracer:
    return trace.get_tracer(__name__)


def _record_stage(stage: str, start: float) -> None:
    duration_ms = (time.perf_counter() - start) * 1000
    metrics.get_meter(__name__).create_histogram(
        "clearcut_stage_latency_ms", unit="ms", description="Pipeline stage latency"
    ).record(duration_ms, {"stage": stage})


def _refresh_tracker_items_gauge(items: list[TrackerItem]) -> None:
    gauge = metrics.get_meter(__name__).create_gauge(
        "clearcut_tracker_items", description="Tracker items by state, refreshed on every write"
    )
    counts = Counter(item.state.value for item in items)
    for state, count in counts.items():
        gauge.set(count, {"state": state})


class InMemoryScriptIngestion:
    """Implements `ScriptIngestion`: always returns the planted scenes."""

    def parse(self, gcs_uri: str, script_id: str) -> list[Scene]:
        start = time.perf_counter()
        with stage_span(_tracer(), "ingest"):
            scenes = list(scenario.SCENES)
        _record_stage("ingest", start)
        return scenes


class InMemorySceneExtractor:
    """Implements `SceneExtractor`: always returns the two planted IP findings."""

    def extract(self, scenes: list[Scene], jurisdiction: Jurisdiction) -> list[Finding]:
        start = time.perf_counter()
        with stage_span(_tracer(), "extract"):
            findings = list(scenario.EXTRACTED_FINDINGS)
        _record_stage("extract", start)
        return findings


class InMemoryLegalGrounding:
    """Implements `LegalGrounding`: always returns the one planted grounded answer."""

    def ground(self, query: str, jurisdiction: Jurisdiction) -> GroundedAnswer:
        start = time.perf_counter()
        with stage_span(_tracer(), "ground"):
            answer = scenario.GROUNDED_ANSWER
        _record_stage("ground", start)
        return answer


class InMemoryWebGrounding:
    """Implements `WebGrounding`: always returns the one planted web answer.

    Its own `web_search` span and stage metric, for the same reason every
    other class here carries one: a Grafana trace of a mocked demo run (D36)
    has to look like a live run, and the live `ParallelWebSearch` records both.
    """

    def search(self, question: str, jurisdiction: Jurisdiction) -> GroundedAnswer:
        start = time.perf_counter()
        with stage_span(_tracer(), "web_search"):
            answer = scenario.WEB_ANSWER
        _record_stage("web_search", start)
        return answer


class InMemoryRightsResearch:
    """Implements `RightsResearch`: the planted claim for the asset named."""

    def find(self, asset_name: str, category: Category, jurisdiction: Jurisdiction) -> RightsClaim:
        start = time.perf_counter()
        with stage_span(_tracer(), "research"):
            claim = scenario.RIGHTS_CLAIMS_BY_ASSET[asset_name]
        _record_stage("research", start)
        return claim


class InMemoryContinuityCheck:
    """Implements `ContinuityCheck`: the planted contradiction, on its one scene."""

    def check(self, scene: Scene, facts: list[BibleFact]) -> Finding | None:
        return scenario.CONTINUITY_FINDINGS_BY_SCENE.get(scene.number)


class InMemoryLoreStore:
    """Implements `LoreStore` over an in-process dict, pre-seeded for the demo
    project. `search` on any other `project_id` returns no facts -- the
    unindexed-project path CP-040's wording depends on."""

    def __init__(self) -> None:
        self._records: dict[str, list[BibleFact | Scene]] = {
            scenario.PROJECT_ID: list(scenario.BIBLE_FACTS)
        }

    def index(self, project_id: str, records: list[BibleFact | Scene]) -> None:
        self._records.setdefault(project_id, []).extend(records)

    def search(self, project_id: str, query: str, limit: int) -> list[BibleFact]:
        return self.facts(project_id)[:limit]

    def facts(self, project_id: str) -> list[BibleFact]:
        records = self._records.get(project_id, [])
        return [record for record in records if isinstance(record, BibleFact)]


class InMemoryProjectStore:
    """Implements `ProjectStore`, pre-seeded with the demo project.

    Every other project id answers `RecordNotFound`, the same shape
    `ClickHouseProjectStore` gives an id nothing was written under.
    """

    def __init__(self) -> None:
        self._projects: dict[str, Project] = {
            scenario.PROJECT_ID: scenario.SEEDED_PROJECT,
        }

    def save(self, project: Project) -> None:
        self._projects[project.project_id] = project

    def get(self, project_id: str) -> Project:
        project = self._projects.get(project_id)
        if project is None:
            raise RecordNotFound(f"no project found for project_id={project_id!r}")
        return project

    def all(self) -> list[Project]:
        return list(self._projects.values())


class InMemoryProjectFavourites:
    """Implements `ProjectFavourites` over an in-process dict.

    Mock mode has no workspace and no grants, so "a project this user can
    read" is "a project this store knows about": `add_favourite` asks
    `InMemoryProjectStore` for it and lets the `RecordNotFound` it raises
    through, which is the same 404 the live path answers a project outside
    the caller's workspace with. Sharing the one store rather than keeping a
    second list of ids is what makes a project created in this process
    favouritable in the same request cycle.
    """

    def __init__(self, projects: InMemoryProjectStore) -> None:
        self._projects = projects
        self._marked: dict[str, set[str]] = {}

    def favourites(self, user_id: str) -> set[str]:
        return set(self._marked.get(user_id, set()))

    def add_favourite(self, user_id: str, project_id: str) -> None:
        self._projects.get(project_id)
        self._marked.setdefault(user_id, set()).add(project_id)

    def remove_favourite(self, user_id: str, project_id: str) -> None:
        self._marked.get(user_id, set()).discard(project_id)


class InMemoryScriptStore:
    """Implements `ScriptStore` over one in-process list, pre-seeded with the
    demo project's planted version 1 (D36's fourth criterion).

    `InMemoryTrackerStore` writes and reads the same rows through
    `record_script` / `latest_script`, exactly as the two ClickHouse stores
    share the `script_versions` table: two in-memory copies would let a
    version written by an analysis be invisible to the read that serves it.
    """

    def __init__(self) -> None:
        self._scripts: list[Script] = [scenario.SEEDED_SCRIPT]

    def save(self, script: Script) -> None:
        self._scripts.append(script)

    def get(self, project_id: str, script_id: str) -> Script:
        for script in self._scripts:
            if script.project_id == project_id and script.script_id == script_id:
                return script
        raise RecordNotFound(
            f"no script found for project_id={project_id!r} script_id={script_id!r}"
        )

    def for_project(self, project_id: str) -> list[Script]:
        found = [script for script in self._scripts if script.project_id == project_id]
        return sorted(found, key=lambda script: script.version)

    def latest(self, project_id: str) -> Script | None:
        versions = self.for_project(project_id)
        return versions[-1] if versions else None


class InMemoryFindingStore:
    """Implements `FindingStore`, keyed by script version like the real one.

    Nothing is pre-seeded: the planted findings are what an analysis
    produces, and pre-loading them would make a script that was never
    analyzed read as though it had been.
    """

    def __init__(self) -> None:
        self._by_script: dict[tuple[str, str], list[Finding]] = {}

    def save(self, project_id: str, script_id: str, findings: list[Finding]) -> None:
        self._by_script.setdefault((project_id, script_id), []).extend(findings)

    def for_script(self, project_id: str, script_id: str) -> list[Finding]:
        return list(self._by_script.get((project_id, script_id), []))


class InMemoryAnalysisJobStore:
    """Implements `AnalysisJobStore`: latest write wins per `(project, analysis)`.

    The real table keeps every version and reads the highest; keeping only
    the newest is the same answer for a store nothing reads history out of.
    """

    def __init__(self) -> None:
        self._jobs: dict[tuple[str, str], AnalysisJob] = {}

    def save(self, job: AnalysisJob) -> None:
        self._jobs[(job.project_id, job.analysis_id)] = job

    def get(self, project_id: str, analysis_id: str) -> AnalysisJob:
        job = self._jobs.get((project_id, analysis_id))
        if job is None:
            raise RecordNotFound(
                f"no analysis found for project_id={project_id!r} analysis_id={analysis_id!r}"
            )
        return job


class InMemoryScriptStorage:
    """Implements `ScriptStorage`: keeps the bytes in memory and answers with
    a `gs://` URI shaped like the one Cloud Storage returns.

    The demo bucket name is the same one `scenario.GCS_URI` uses, so an
    upload in mock mode produces a URI the planted ingestion recognises.
    """

    def __init__(self) -> None:
        self.stored: list[tuple[str, str, bytes]] = []

    def store(self, project_id: str, filename: str, content: bytes) -> str:
        self.stored.append((project_id, filename, content))
        return f"gs://{_DEMO_BUCKET}/{project_id}/{filename}"


class InMemoryTrackerStore:
    """Implements `TrackerStore` over an in-process dict plus the script rows
    `InMemoryScriptStore` owns, so a transition written with `save` comes back
    from `latest` and `latest_for_project` in the state it was written -- the
    property `PATCH .../tracker-items/{item_id}` needs.

    `latest` is keyed by `(project_id, item_id)`: item ids are unique only
    inside their project, so a lookup on the id alone would answer with
    whichever project wrote `EVT-001` last (ADR 0014)."""

    def __init__(self, scripts: InMemoryScriptStore | None = None) -> None:
        self._items: dict[tuple[str, str], TrackerItem] = {}
        self._lock = RLock()
        self._events: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._scripts = scripts if scripts is not None else InMemoryScriptStore()

    def save(self, items: list[TrackerItem]) -> None:
        start = time.perf_counter()
        with stage_span(_tracer(), "track"):
            for item in items:
                self._items[(item.project_id, item.item_id)] = item
        _record_stage("track", start)
        _refresh_tracker_items_gauge(items)

    def compare_save(self, item: TrackerItem, expected_version: int, actor: str) -> None:
        with self._lock:
            current = self.latest(item.project_id, item.item_id)
            if current.version != expected_version or item.version != expected_version + 1:
                raise TrackerConflict(current.version)
            self.save([item])
            self._events.setdefault((item.project_id, item.item_id), []).append(
                {
                    "event_id": f"clearance-{item.project_id}-{item.item_id}-{item.version}",
                    "actor": actor,
                    "version": item.version,
                    "previous_version": expected_version,
                    "at": item.updated_at,
                    "item": asdict(item),
                }
            )

    def history(
        self, project_id: str, item_id: str, before_version: int | None = None
    ) -> list[dict[str, Any]]:
        self.latest(project_id, item_id)
        with self._lock:
            events = self._events.get((project_id, item_id), [])
            return [
                event
                for event in reversed(events)
                if before_version is None or event["version"] < before_version
            ][:50]

    def latest(self, project_id: str, item_id: str) -> TrackerItem:
        item = self._items.get((project_id, item_id))
        if item is None:
            raise RecordNotFound(
                f"no tracker item found for project_id={project_id!r} item_id={item_id!r}"
            )
        return item

    def latest_for_project(self, project_id: str) -> list[TrackerItem]:
        return [item for item in self._items.values() if item.project_id == project_id]

    def summaries_for_projects(self, project_ids: Sequence[str]) -> dict[str, ClearanceSummary]:
        """Implements `ClearanceSummaries`: one pass over the dict, for every
        project asked about at once.

        Genuinely one round trip, because there is no trip -- which is the
        point of keeping the port's promise here too. Mock mode draws the same
        list screen as live mode, so a route that asked once per project would
        still be a route the demo could not exercise.

        Only the ids it was given are counted, and an id with no items is left
        out rather than returned as zero -- the same contract
        `FirestoreTrackerStore` answers, so the route cannot tell the two
        apart.
        """
        wanted = {project_id for project_id in project_ids if project_id}
        grouped: dict[str, list[TrackerItem]] = {}
        with self._lock:
            for item in self._items.values():
                if item.project_id in wanted:
                    grouped.setdefault(item.project_id, []).append(item)
        return {project_id: clearance_summary(items) for project_id, items in grouped.items()}

    def record_script(self, script: Script) -> None:
        self._scripts.save(script)

    def latest_script(self, project_id: str) -> Script | None:
        return self._scripts.latest(project_id)


class InMemoryNotifier:
    """Implements `Notifier`: records the call in memory instead of reaching a
    webhook, so the demo's actions beat completes rather than 502s."""

    def __init__(self) -> None:
        self.notifications: list[tuple[TrackerItem, str]] = []

    def notify(self, item: TrackerItem, reason: str) -> None:
        self.notifications.append((item, reason))
