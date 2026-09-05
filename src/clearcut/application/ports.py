"""The thirteen ports the parallel verticals implement (docs/plan/sdd.md
Section 3).

Each port exists because it crosses a real I/O boundary: an HTTPS call to
Document AI, Gemini, Vertex AI Search, or the Parallel Task API, a BigQuery
read/write, a ClickHouse read/write, a Cloud Storage read/write, or an
outbound webhook (AGENT.md Section 4 — a port only for a real boundary).
`composition.py` is the only place a concrete adapter is wired to one of
these.

`TrackerStore` and `Notifier` cover the tracker's two boundaries: versioned
persistence over ClickHouse, and producer notification over an outbound
webhook (docs/plan/sdd.md Section 3).

`ContinuityCheck` is its own narrow port rather than a second `SceneExtractor`
call: `SceneExtractor.extract(scenes, jurisdiction)` has no parameter for the
bible facts a contradiction check needs, so it earns a separate network call
against a different model (docs/plan/agentic-workflow.md Section 2.2).

The five stores added for the REST surface — `ProjectStore`, `ScriptStore`,
`FindingStore`, `AnalysisJobStore` and `ScriptStorage` — each cross the same
kind of boundary the first eight do. They are separate ports rather than
methods on `TrackerStore` because a route that reads scripts has no business
holding the tracker's writes (AGENT.md Section 3, ISP).
"""

import enum
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from clearcut.domain.analysis import AnalysisJob
from clearcut.domain.bible import BibleFact
from clearcut.domain.finding import Category, Citation, Finding
from clearcut.domain.jurisdiction import Jurisdiction
from clearcut.domain.project import Project
from clearcut.domain.script import Scene, Script
from clearcut.domain.tracker import TrackerItem


class Confidence(enum.StrEnum):
    """How sure an adapter is about a value it resolved from the outside world.

    Carries no risk rule of its own: the confidence-to-risk mapping belongs
    to `AnalyzeScript` (docs/plan/sdd.md Section 4.1 step 5), not to a port.
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True)
class GroundedAnswer:
    """A `LegalGrounding` answer, always carrying the citations it rests on."""

    text: str
    citations: tuple[Citation, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RightsClaim:
    """A `RightsResearch` result for one asset."""

    holder: str
    contact: str
    litigation_posture: str
    confidence: Confidence
    citations: tuple[Citation, ...] = field(default_factory=tuple)


@runtime_checkable
class ScriptIngestion(Protocol):
    """Turns an uploaded screenplay into scenes with page anchors."""

    def parse(self, gcs_uri: str, script_id: str) -> list[Scene]: ...


@runtime_checkable
class SceneExtractor(Protocol):
    """Extracts clearance findings from a batch of scenes."""

    def extract(self, scenes: list[Scene], jurisdiction: Jurisdiction) -> list[Finding]: ...


@runtime_checkable
class LegalGrounding(Protocol):
    """Grounds a legal question in one jurisdiction's corpus, with citations."""

    def ground(self, query: str, jurisdiction: Jurisdiction) -> GroundedAnswer: ...


@runtime_checkable
class RightsResearch(Protocol):
    """Resolves the rights holder for one asset."""

    def find(
        self, asset_name: str, category: Category, jurisdiction: Jurisdiction
    ) -> RightsClaim: ...


@runtime_checkable
class LoreStore(Protocol):
    """Indexes and retrieves project-scoped bible facts and scenes."""

    def index(self, project_id: str, records: list[BibleFact | Scene]) -> None: ...

    def search(self, project_id: str, query: str, limit: int) -> list[BibleFact]: ...


@runtime_checkable
class TrackerStore(Protocol):
    """Persists tracker items and script versions over ClickHouse.

    Both tables live behind one port: the versioned `TrackerItem` rows and
    the `script_versions` side EvaluateDelta reads (docs/plan/sdd.md
    Section 3).
    """

    def save(self, items: list[TrackerItem]) -> None: ...

    def latest(self, item_id: str) -> TrackerItem: ...

    def latest_for_project(self, project_id: str) -> list[TrackerItem]: ...

    def record_script(self, script: Script) -> None: ...

    def latest_script(self, project_id: str) -> Script | None: ...


@runtime_checkable
class Notifier(Protocol):
    """Notifies a producer over an outbound webhook."""

    def notify(self, item: TrackerItem, reason: str) -> None: ...


@runtime_checkable
class ContinuityCheck(Protocol):
    """Checks one scene against a batch of Project Bible facts (D11)."""

    def check(self, scene: Scene, facts: list[BibleFact]) -> Finding | None: ...


@runtime_checkable
class ProjectStore(Protocol):
    """Persists projects over ClickHouse.

    `GET /api/projects` is the first screen the SPA draws, so the project
    list is a read of its own rather than something derived from the tracker
    rows a project happens to own.
    """

    def save(self, project: Project) -> None: ...

    def get(self, project_id: str) -> Project: ...

    def all(self) -> list[Project]: ...


@runtime_checkable
class ScriptStore(Protocol):
    """Persists script versions and their scenes over ClickHouse.

    The script rows `EvaluateDelta` diffs against still live behind
    `TrackerStore.record_script` / `latest_script`; moving them here is a
    change to that adapter and belongs with it. This port serves the read
    side the REST surface needs: one version by id, every version of a
    project, and the newest one.
    """

    def save(self, script: Script) -> None: ...

    def get(self, project_id: str, script_id: str) -> Script: ...

    def for_project(self, project_id: str) -> list[Script]: ...

    def latest(self, project_id: str) -> Script | None: ...


@runtime_checkable
class FindingStore(Protocol):
    """Persists the findings of one analysis over ClickHouse.

    Findings are stored per script version, not per project: reopening an
    older version must show what that version triggered, not what the newest
    one does.
    """

    def save(self, project_id: str, script_id: str, findings: list[Finding]) -> None: ...

    def for_script(self, project_id: str, script_id: str) -> list[Finding]: ...


@runtime_checkable
class AnalysisJobStore(Protocol):
    """Persists analysis jobs over ClickHouse.

    The upload answers 202 and the browser polls `get`, so this row is the
    only thing that knows whether a run that started is still running
    (`domain/analysis.py`).
    """

    def save(self, job: AnalysisJob) -> None: ...

    def get(self, project_id: str, analysis_id: str) -> AnalysisJob: ...


@runtime_checkable
class ScriptStorage(Protocol):
    """Writes an uploaded screenplay to Cloud Storage.

    Returns the `gs://` URI `ScriptIngestion.parse` reads back, which is why
    the bytes cross a boundary here rather than being passed between the two
    in memory: Document AI reads the object from the bucket, not from this
    process.
    """

    def store(self, project_id: str, filename: str, content: bytes) -> str: ...
