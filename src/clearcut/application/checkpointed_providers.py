"""Provider-specific checkpoint values, with no mutable result publication."""

from dataclasses import asdict

from clearcut.application.analysis_documents import finding_data, read_finding, scene_data
from clearcut.application.analysis_steps import AnalysisSteps
from clearcut.application.ports import (
    ContinuityCheck,
    GroundedAnswer,
    LegalGrounding,
    LoreStore,
    SceneExtractor,
)
from clearcut.domain.bible import BibleFact
from clearcut.domain.finding import Citation, Finding
from clearcut.domain.jurisdiction import Jurisdiction
from clearcut.domain.script import Scene


class CheckpointedExtractor:
    def __init__(self, provider: SceneExtractor, steps: AnalysisSteps) -> None:
        self.provider, self.steps = provider, steps

    def extract(self, scenes: list[Scene], jurisdiction: Jurisdiction) -> list[Finding]:
        return self.steps.run(
            "extraction",
            [[scene_data(scene) for scene in scenes], jurisdiction.code],
            lambda: self.provider.extract(scenes, jurisdiction),
            lambda findings: {"findings": [finding_data(finding) for finding in findings]},
            lambda data: [read_finding(finding) for finding in data["findings"]],
        )


class CheckpointedGrounding:
    def __init__(self, provider: LegalGrounding, steps: AnalysisSteps) -> None:
        self.provider, self.steps = provider, steps

    def ground(self, query: str, jurisdiction: Jurisdiction) -> GroundedAnswer:
        return self.steps.run(
            "grounding",
            [query, jurisdiction.code],
            lambda: self.provider.ground(query, jurisdiction),
            asdict,
            lambda data: GroundedAnswer(
                data["text"], tuple(Citation(**citation) for citation in data["citations"])
            ),
        )


class CheckpointedContinuity:
    def __init__(self, provider: ContinuityCheck, steps: AnalysisSteps) -> None:
        self.provider, self.steps = provider, steps

    def check(self, scene: Scene, facts: list[BibleFact]) -> Finding | None:
        return self.steps.run(
            "continuity",
            [scene_data(scene), [asdict(fact) for fact in facts]],
            lambda: self.provider.check(scene, facts),
            lambda finding: {"finding": finding_data(finding) if finding else None},
            lambda data: read_finding(data["finding"]) if data["finding"] else None,
        )


class CheckpointedLore:
    def __init__(self, provider: LoreStore, steps: AnalysisSteps) -> None:
        self.provider, self.steps = provider, steps

    def search(self, project_id: str, query: str, limit: int) -> list[BibleFact]:
        return self.steps.run(
            "bible_context",
            [project_id, query, limit],
            lambda: self.provider.search(project_id, query, limit),
            lambda facts: {"facts": [asdict(fact) for fact in facts]},
            lambda data: [BibleFact(**fact) for fact in data["facts"]],
        )

    def facts(self, project_id: str) -> list[BibleFact]:
        return self.steps.run(
            "bible_snapshot",
            project_id,
            lambda: self.provider.facts(project_id),
            lambda facts: {"facts": [asdict(fact) for fact in facts]},
            lambda data: [BibleFact(**fact) for fact in data["facts"]],
        )

    def index(self, project_id: str, records: list[BibleFact | Scene]) -> None:
        raise RuntimeError("durable analysis indexes lore only after publication")
