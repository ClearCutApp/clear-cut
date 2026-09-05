"""Hand-written fakes for the application ports (AGENT.md Section 5).

No `unittest.mock` patching: each fake implements its port directly, in
plain Python, so a port-conformance test can assert `isinstance(fake, Port)`
and a future use-case test can inject one without touching real I/O.
"""

from clearcut.application.ports import (
    AnalysisJobStore,
    Confidence,
    FindingStore,
    GroundedAnswer,
    LegalGrounding,
    LoreStore,
    ProjectStore,
    RightsClaim,
    RightsResearch,
    SceneExtractor,
    ScriptIngestion,
    ScriptStorage,
    ScriptStore,
)
from clearcut.domain.analysis import AnalysisJob
from clearcut.domain.bible import BibleFact
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.finding import Category, Finding
from clearcut.domain.jurisdiction import Jurisdiction
from clearcut.domain.project import Project
from clearcut.domain.script import Scene, Script


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


class FakeProjectStore:
    def __init__(self, projects: list[Project] | None = None) -> None:
        self._projects: dict[str, Project] = {
            project.project_id: project for project in (projects or [])
        }

    def save(self, project: Project) -> None:
        self._projects[project.project_id] = project

    def get(self, project_id: str) -> Project:
        try:
            return self._projects[project_id]
        except KeyError:
            raise RecordNotFound(f"no project {project_id!r}") from None

    def all(self) -> list[Project]:
        return list(self._projects.values())


class FakeScriptStore:
    def __init__(self, scripts: list[Script] | None = None) -> None:
        self._scripts: list[Script] = list(scripts or [])

    def save(self, script: Script) -> None:
        self._scripts.append(script)

    def get(self, project_id: str, script_id: str) -> Script:
        for script in self._scripts:
            if script.project_id == project_id and script.script_id == script_id:
                return script
        raise RecordNotFound(f"no script {script_id!r} in project {project_id!r}")

    def for_project(self, project_id: str) -> list[Script]:
        return [script for script in self._scripts if script.project_id == project_id]

    def latest(self, project_id: str) -> Script | None:
        versions = self.for_project(project_id)
        return max(versions, key=lambda script: script.version) if versions else None


class FakeFindingStore:
    def __init__(self) -> None:
        self._findings_by_script: dict[tuple[str, str], list[Finding]] = {}

    def save(self, project_id: str, script_id: str, findings: list[Finding]) -> None:
        self._findings_by_script.setdefault((project_id, script_id), []).extend(findings)

    def for_script(self, project_id: str, script_id: str) -> list[Finding]:
        return list(self._findings_by_script.get((project_id, script_id), []))


class FakeAnalysisJobStore:
    def __init__(self, jobs: list[AnalysisJob] | None = None) -> None:
        self._jobs: dict[tuple[str, str], AnalysisJob] = {
            (job.project_id, job.analysis_id): job for job in (jobs or [])
        }

    def save(self, job: AnalysisJob) -> None:
        self._jobs[(job.project_id, job.analysis_id)] = job

    def get(self, project_id: str, analysis_id: str) -> AnalysisJob:
        try:
            return self._jobs[(project_id, analysis_id)]
        except KeyError:
            raise RecordNotFound(f"no analysis {analysis_id!r} in project {project_id!r}") from None


class FakeScriptStorage:
    """Records what it was handed and returns a `gs://` URI shaped like the
    real one, so a caller can assert on the URI without a bucket."""

    def __init__(self, bucket: str = "clearcut-scripts") -> None:
        self._bucket = bucket
        self.stored: list[tuple[str, str, bytes]] = []

    def store(self, project_id: str, filename: str, content: bytes) -> str:
        self.stored.append((project_id, filename, content))
        return f"gs://{self._bucket}/{project_id}/{filename}"


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
_project_store: ProjectStore = FakeProjectStore()
_script_store: ScriptStore = FakeScriptStore()
_finding_store: FindingStore = FakeFindingStore()
_analysis_job_store: AnalysisJobStore = FakeAnalysisJobStore()
_script_storage: ScriptStorage = FakeScriptStorage()
