"""What the six route suites share: a client builder, sample records, and the
two doubles that stand in for a use case rather than for a port.

Each domain suite mounts its own blueprint over real use cases wired to
hand-written fakes, so a happy path exercises the whole route-to-port path
and not a stub of it. Error mapping is proven the other way round, by
substituting `RaisingUseCase` for one argument of the factory under test:
that isolates the route's own status mapping from any real use case's
behaviour.

No `unittest.mock` anywhere (AGENT.md Section 5). `tests/unit/fakes.py`
already carries the store fakes bound to their ports; the two this file adds
are the ones that file has no need for.
"""

from datetime import UTC, datetime
from typing import Any

from flask import Blueprint, Flask
from flask.testing import FlaskClient

from clearcut.application.ports import Notifier, TrackerStore
from clearcut.domain.analysis import AnalysisJob, AnalysisState
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.finding import Category, Citation, Finding, NerLabel, RiskLevel
from clearcut.domain.project import Project
from clearcut.domain.script import Scene, Script
from clearcut.domain.tracker import TrackerItem, TrackerState

AT = "2026-09-05T12:00:00Z"
MOMENT = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
PROJECT_ID = "prj-1"
CITATION = Citation(uri="https://example.test/law", title="Ley 11.723", snippet="art. 1")


def client(*blueprints: Blueprint) -> FlaskClient:
    """A test client over `blueprints`, registered in the order given."""
    app = Flask(__name__)
    for blueprint in blueprints:
        app.register_blueprint(blueprint)
    return app.test_client()


def routes_of(*blueprints: Blueprint) -> set[tuple[str, str]]:
    """Every `(rule, method)` `blueprints` register, less Flask's own.

    `HEAD` and `OPTIONS` are dropped because Flask adds both itself; a suite
    asserting on them would be asserting about Flask.
    """
    app = Flask(__name__)
    for blueprint in blueprints:
        app.register_blueprint(blueprint)
    return {
        (str(rule), method)
        for rule in app.url_map.iter_rules()
        if rule.endpoint != "static"
        for method in rule.methods or set()
        if method not in {"HEAD", "OPTIONS"}
    }


def scene(number: int = 1, text: str = "A neon Quilmes sign glows.") -> Scene:
    return Scene(
        number=number,
        heading=f"INT. BAR {number} - DAY",
        page_start=number,
        page_end=number,
        text=text,
    )


def finding(**overrides: Any) -> Finding:
    fields: dict[str, Any] = dict(
        finding_id="EVT-001",
        scene_number=1,
        page=1,
        raw_text="Quilmes",
        category=Category.INDUSTRIAL_PROPERTY,
        ner_label=NerLabel.BRAND,
        risk_level=RiskLevel.MEDIUM,
        required_document="Trademark Clearance Form",
        citations=(CITATION,),
    )
    fields.update(overrides)
    return Finding(**fields)


def tracker_item(item_id: str = "EVT-001", project_id: str = PROJECT_ID, **kw: Any) -> TrackerItem:
    fields: dict[str, Any] = dict(
        item_id=item_id,
        project_id=project_id,
        finding_id="EVT-001",
        scene_numbers=(1,),
        state=TrackerState.BLOCKED,
        required_document="Sync License",
        contact="rights@example.test",
        litigation_posture="none on record",
        note="",
        updated_at=AT,
        version=1,
    )
    fields.update(kw)
    return TrackerItem(**fields)


def project(project_id: str = PROJECT_ID, **kw: Any) -> Project:
    fields: dict[str, Any] = dict(
        project_id=project_id,
        title="El Ultimo Verano",
        jurisdiction_code="AR",
        created_at=AT,
    )
    fields.update(kw)
    return Project(**fields)


def script(script_id: str = "scr-1", project_id: str = PROJECT_ID, **kw: Any) -> Script:
    fields: dict[str, Any] = dict(
        script_id=script_id,
        project_id=project_id,
        version=1,
        gcs_uri="gs://clearcut-scripts/v1.pdf",
        jurisdiction_code="AR",
        scenes=[scene()],
    )
    fields.update(kw)
    return Script(**fields)


def analysis_job(analysis_id: str = "ana-1", **kw: Any) -> AnalysisJob:
    fields: dict[str, Any] = dict(
        analysis_id=analysis_id,
        project_id=PROJECT_ID,
        script_id="scr-1",
        state=AnalysisState.QUEUED,
        created_at=MOMENT,
        updated_at=MOMENT,
    )
    fields.update(kw)
    return AnalysisJob(**fields)


class FakeTrackerStore:
    """`latest` raises `RecordNotFound` for an unknown pair, the same domain
    error `ClickHouseTrackerStore` raises, so a happy-path route test
    exercises the real not-found mapping as well."""

    def __init__(self, items: list[TrackerItem] | None = None) -> None:
        self._items: dict[tuple[str, str], TrackerItem] = {
            (item.project_id, item.item_id): item for item in (items or [])
        }
        self.saved: list[list[TrackerItem]] = []
        self.recorded: list[Script] = []
        self._scripts: dict[str, Script] = {}

    def save(self, items: list[TrackerItem]) -> None:
        self.saved.append(list(items))
        for item in items:
            self._items[(item.project_id, item.item_id)] = item

    def latest(self, project_id: str, item_id: str) -> TrackerItem:
        item = self._items.get((project_id, item_id))
        if item is None:
            raise RecordNotFound(f"no tracker item {item_id!r} in project {project_id!r}")
        return item

    def latest_for_project(self, project_id: str) -> list[TrackerItem]:
        return [item for item in self._items.values() if item.project_id == project_id]

    def record_script(self, script_version: Script) -> None:
        self.recorded.append(script_version)
        self._scripts[script_version.project_id] = script_version

    def latest_script(self, project_id: str) -> Script | None:
        return self._scripts.get(project_id)


class FakeNotifier:
    def __init__(self) -> None:
        self.calls: list[tuple[TrackerItem, str]] = []

    def notify(self, item: TrackerItem, reason: str) -> None:
        self.calls.append((item, reason))


class RaisingUseCase:
    """A fake *use case*, not a fake port: whatever it is called with, it
    raises. Substituted for one argument of a blueprint factory to prove the
    route's own error-to-status mapping independently of any real use case."""

    def __init__(self, error: Exception) -> None:
        self._error = error
        self.calls: list[tuple[Any, ...]] = []

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append(args)
        raise self._error


class RecordingUseCase:
    """A fake *use case* that records every call and returns `result`."""

    def __init__(self, result: Any = None) -> None:
        self._result = result
        self.calls: list[tuple[Any, ...]] = []

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append(args)
        return self._result


# Bound to their ports by annotated assignment, the same way
# `tests/unit/fakes.py` binds its own: `isinstance` cannot see parameter
# order or types, and mypy checks this structurally.
_tracker: TrackerStore = FakeTrackerStore()
_notifier: Notifier = FakeNotifier()
