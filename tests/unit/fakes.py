"""Hand-written fakes for the application ports (AGENT.md Section 5).

No `unittest.mock` patching: each fake implements its port directly, in
plain Python, so a port-conformance test can assert `isinstance(fake, Port)`
and a future use-case test can inject one without touching real I/O.
"""

from clearcut.application.ports import (
    Confidence,
    GroundedAnswer,
    LegalGrounding,
    LoreStore,
    RightsClaim,
    RightsResearch,
    SceneExtractor,
    ScriptIngestion,
)
from clearcut.domain.bible import BibleFact
from clearcut.domain.finding import Category, Finding
from clearcut.domain.jurisdiction import Jurisdiction
from clearcut.domain.script import Scene


class FakeScriptIngestion:
    def __init__(self, scenes: list[Scene] | None = None) -> None:
        self._scenes = scenes if scenes is not None else []

    def parse(self, gcs_uri: str, script_id: str) -> list[Scene]:
        return list(self._scenes)


class FakeSceneExtractor:
    def __init__(self, findings: list[Finding] | None = None) -> None:
        self._findings = findings if findings is not None else []

    def extract(self, scenes: list[Scene], jurisdiction: Jurisdiction) -> list[Finding]:
        return list(self._findings)


class FakeLegalGrounding:
    def __init__(self, answer: GroundedAnswer | None = None) -> None:
        self._answer = answer if answer is not None else GroundedAnswer(text="", citations=())

    def ground(self, query: str, jurisdiction: Jurisdiction) -> GroundedAnswer:
        return self._answer


class FakeRightsResearch:
    def __init__(self, claim: RightsClaim | None = None) -> None:
        self._claim = (
            claim
            if claim is not None
            else RightsClaim(
                holder="",
                contact="",
                litigation_posture="",
                confidence=Confidence.LOW,
                citations=(),
            )
        )

    def find(self, asset_name: str, category: Category, jurisdiction: Jurisdiction) -> RightsClaim:
        return self._claim


class FakeLoreStore:
    def __init__(self) -> None:
        self._records_by_project: dict[str, list[BibleFact | Scene]] = {}

    def index(self, project_id: str, records: list[BibleFact | Scene]) -> None:
        self._records_by_project.setdefault(project_id, []).extend(records)

    def search(self, project_id: str, query: str, limit: int) -> list[BibleFact]:
        records = self._records_by_project.get(project_id, [])
        facts = [record for record in records if isinstance(record, BibleFact)]
        return facts[:limit]


# Each fake bound to its port by an annotated assignment (CP-012, D3).
# `isinstance` (tests/unit/application/test_ports.py) proves the required
# methods exist; it cannot see parameter names, order, or types. mypy checks
# this assignment structurally, so a fake whose method signature drifts from
# its port — an argument reordered, a type widened — fails here even though
# it would still pass `isinstance`.
_ingestion: ScriptIngestion = FakeScriptIngestion()
_extractor: SceneExtractor = FakeSceneExtractor()
_grounding: LegalGrounding = FakeLegalGrounding()
_research: RightsResearch = FakeRightsResearch()
_lore_store: LoreStore = FakeLoreStore()
