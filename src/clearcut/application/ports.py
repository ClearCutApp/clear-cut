"""The five ports the parallel verticals implement (docs/plan/sdd.md Section 3).

Each port exists because it crosses a real I/O boundary: an HTTPS call to
Document AI, Gemini, Vertex AI Search, or the Parallel Task API, or a
BigQuery read/write (AGENT.md Section 4 — a port only for a real boundary).
`composition.py` is the only place a concrete adapter is wired to one of
these.

`TrackerStore` and `Notifier` are not declared here. They have no caller and
no parallel implementer to coordinate with until phase 4; declaring them now
would be an interface with zero callers. They arrive with their adapters.
"""

import enum
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from clearcut.domain.bible import BibleFact
from clearcut.domain.finding import Category, Citation, Finding
from clearcut.domain.jurisdiction import Jurisdiction
from clearcut.domain.script import Scene


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
