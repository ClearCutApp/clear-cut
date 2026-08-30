"""The eight ports the parallel verticals implement (docs/plan/sdd.md Section 3).

Each port exists because it crosses a real I/O boundary: an HTTPS call to
Document AI, Gemini, Vertex AI Search, or the Parallel Task API, a BigQuery
read/write, a ClickHouse read/write, or an outbound webhook (AGENT.md
Section 4 — a port only for a real boundary). `composition.py` is the only
place a concrete adapter is wired to one of these.

`TrackerStore` and `Notifier` cover the tracker's two boundaries: versioned
persistence over ClickHouse, and producer notification over an outbound
webhook (docs/plan/sdd.md Section 3).

`ContinuityCheck` is its own narrow port rather than a second `SceneExtractor`
call: `SceneExtractor.extract(scenes, jurisdiction)` has no parameter for the
bible facts a contradiction check needs, so it earns a separate network call
against a different model (docs/plan/agentic-workflow.md Section 2.2).
"""

import enum
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from clearcut.domain.bible import BibleFact
from clearcut.domain.finding import Category, Citation, Finding
from clearcut.domain.jurisdiction import Jurisdiction
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
