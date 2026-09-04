"""Unit tests for the five demo-path HTTP routes (CP-029, docs/plan/sdd.md
Section 4.2; AGENT.md Section 2 -- "the route only maps HTTP to use-case
input/output, and holds no orchestration").

Real use cases wired over hand-written fake ports (AGENT.md Section 5) drive
every happy path -- no `unittest.mock`, no network, no live Flask server.
Error mapping is proven by substituting a fake *use case* (an object with
just an `execute` that raises) for one of `create_blueprint`'s four
arguments, per this checkpoint's own criteria.
"""

import ast
from pathlib import Path
from typing import Any, cast

import pytest
from flask import Flask
from flask.testing import FlaskClient

from clearcut.adapters.http.routes import create_blueprint
from clearcut.application.analyze_script import AnalysisReport, AnalyzeScript
from clearcut.application.answer_project_question import AnswerProjectQuestion
from clearcut.application.evaluate_delta import EvaluateDelta
from clearcut.application.list_tracker_items import ListTrackerItems
from clearcut.application.ports import Confidence, GroundedAnswer, RightsClaim
from clearcut.application.resolve_finding import ResolveFinding
from clearcut.domain.errors import RecordNotFound, SourceUnavailable
from clearcut.domain.finding import Category, Finding, NerLabel, RiskLevel
from clearcut.domain.jurisdiction import Jurisdiction, jurisdiction_for
from clearcut.domain.script import Scene, Script
from clearcut.domain.tracker import TrackerItem, TrackerState

REPO_ROOT = Path(__file__).resolve().parents[3]
ROUTES_PATH = REPO_ROOT / "src" / "clearcut" / "adapters" / "http" / "routes.py"

_MEXICO = jurisdiction_for("MX")
_AT = "2026-08-31T00:00:00Z"


def _scene(number: int = 1) -> Scene:
    return Scene(
        number=number,
        heading="INT. BAR - DAY",
        page_start=number,
        page_end=number,
        text="A neon Quilmes sign glows.",
    )


def _finding(**overrides: Any) -> Finding:
    fields: dict[str, Any] = dict(
        finding_id="placeholder",
        scene_number=1,
        page=1,
        raw_text="Quilmes",
        category=Category.INDUSTRIAL_PROPERTY,
        ner_label=NerLabel.BRAND,
        risk_level=RiskLevel.MEDIUM,
        required_document="Trademark Clearance Form",
    )
    fields.update(overrides)
    return Finding(**fields)


def _item(item_id: str = "itm-1", project_id: str = "proj-1", **overrides: Any) -> TrackerItem:
    fields: dict[str, Any] = dict(
        item_id=item_id,
        project_id=project_id,
        finding_id="EVT-001",
        scene_numbers=(1,),
        state=TrackerState.BLOCKED,
        required_document="Sync License",
        contact="rights@example.com",
        litigation_posture="none on record",
        note="",
        updated_at="2026-08-30T00:00:00Z",
        version=1,
    )
    fields.update(overrides)
    return TrackerItem(**fields)


# ---------------------------------------------------------------------------
# Hand-written fakes, local to this file (matching the convention every other
# use-case test file already sets: test_analyze_script.py, test_resolve_finding.py).
# ---------------------------------------------------------------------------


class _Ingestion:
    def __init__(self, scenes: list[Scene] | None = None) -> None:
        self._scenes = scenes if scenes is not None else [_scene()]
        self.calls: list[tuple[str, str]] = []

    def parse(self, gcs_uri: str, script_id: str) -> list[Scene]:
        self.calls.append((gcs_uri, script_id))
        return list(self._scenes)


class _Extractor:
    def __init__(self, findings: list[Finding] | None = None) -> None:
        self._findings = findings if findings is not None else [_finding()]

    def extract(self, scenes: list[Scene], jurisdiction: Jurisdiction) -> list[Finding]:
        return list(self._findings)


class _Grounding:
    def __init__(self, answer: GroundedAnswer | None = None) -> None:
        self._answer = answer if answer is not None else GroundedAnswer(text="", citations=())
        self.calls: list[tuple[str, Jurisdiction]] = []

    def ground(self, query: str, jurisdiction: Jurisdiction) -> GroundedAnswer:
        self.calls.append((query, jurisdiction))
        return self._answer


class _Research:
    def __init__(self, claim: RightsClaim | None = None) -> None:
        self._claim = (
            claim
            if claim is not None
            else RightsClaim(
                holder="", contact="", litigation_posture="", confidence=Confidence.LOW
            )
        )

    def find(self, asset_name: str, category: Category, jurisdiction: Jurisdiction) -> RightsClaim:
        return self._claim


class _LoreStore:
    def __init__(self) -> None:
        self.searched: list[tuple[str, str, int]] = []

    def index(self, project_id: str, records: list[Any]) -> None:
        return None

    def search(self, project_id: str, query: str, limit: int) -> list[Any]:
        self.searched.append((project_id, query, limit))
        return []


class _Continuity:
    def check(self, scene: Scene, facts: list[Any]) -> Finding | None:
        return None


class _TrackerStore:
    """`latest`, when `items` has no matching row, raises `RecordNotFound` --
    the same domain error the real ClickHouse adapter raises (D23), so a
    happy-path PATCH/notify test exercises the real not-found mapping too.

    `latest_script` returns `previous_script` unconditionally (`None` by
    default), matching the real adapter's per-project scope closely enough
    for these route tests, which only ever wire one project at a time."""

    def __init__(
        self, items: list[TrackerItem] | None = None, previous_script: Script | None = None
    ) -> None:
        self._items = items if items is not None else []
        self._previous_script = previous_script
        self.saved: list[list[TrackerItem]] = []
        self.recorded: list[Script] = []
        self.latest_calls: list[str] = []
        self.latest_for_project_calls: list[str] = []

    def save(self, items: list[TrackerItem]) -> None:
        self.saved.append(list(items))

    def latest(self, item_id: str) -> TrackerItem:
        self.latest_calls.append(item_id)
        matches = [row for row in self._items if row.item_id == item_id]
        if not matches:
            raise RecordNotFound(f"no tracker item: {item_id}")
        return max(matches, key=lambda row: row.version)

    def latest_for_project(self, project_id: str) -> list[TrackerItem]:
        self.latest_for_project_calls.append(project_id)
        return [row for row in self._items if row.project_id == project_id]

    def record_script(self, script: Script) -> None:
        self.recorded.append(script)

    def latest_script(self, project_id: str) -> Script | None:
        return self._previous_script


class _Notifier:
    def __init__(self) -> None:
        self.calls: list[tuple[TrackerItem, str]] = []

    def notify(self, item: TrackerItem, reason: str) -> None:
        self.calls.append((item, reason))


class _RaisingUseCase:
    """A fake *use case* (not a fake port): whatever it is called with, it
    raises `error`. Substituted for one of `create_blueprint`'s five
    arguments to prove the route's own error-to-status mapping, independent
    of any real use case's behaviour."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        raise self._error


class _RecordingUseCase:
    """A fake *use case* that records every call and returns a canned
    `AnalysisReport`. Substituted for `analyze_script` or `evaluate_delta` to
    prove which one the `version` branch calls, independent of either real
    use case's behaviour."""

    def __init__(self, report: AnalysisReport) -> None:
        self._report = report
        self.calls: list[tuple[Any, ...]] = []

    def execute(self, *args: Any, **kwargs: Any) -> AnalysisReport:
        self.calls.append(args)
        return self._report


def _report(version: int = 1) -> AnalysisReport:
    return AnalysisReport(
        script=Script(
            script_id="scr-1",
            project_id="proj-1",
            version=version,
            gcs_uri="gs://bucket/v1.pdf",
            jurisdiction_code="MX",
            scenes=[],
        ),
        findings=(),
        tracker_items=(),
    )


# ---------------------------------------------------------------------------
# App/client builders
# ---------------------------------------------------------------------------


def _analyze_script(
    ingestion: _Ingestion | None = None,
    extractor: _Extractor | None = None,
    grounding: _Grounding | None = None,
    research: _Research | None = None,
    lore: _LoreStore | None = None,
    tracker: _TrackerStore | None = None,
    continuity: _Continuity | None = None,
) -> AnalyzeScript:
    return AnalyzeScript(
        ingestion=ingestion if ingestion is not None else _Ingestion(),
        extractor=extractor if extractor is not None else _Extractor(),
        grounding=grounding if grounding is not None else _Grounding(),
        research=research if research is not None else _Research(),
        lore=lore if lore is not None else _LoreStore(),
        tracker=tracker if tracker is not None else _TrackerStore(),
        continuity=continuity if continuity is not None else _Continuity(),
    )


def _evaluate_delta(
    ingestion: _Ingestion | None = None,
    extractor: _Extractor | None = None,
    grounding: _Grounding | None = None,
    research: _Research | None = None,
    lore: _LoreStore | None = None,
    tracker: _TrackerStore | None = None,
    continuity: _Continuity | None = None,
    notifier: _Notifier | None = None,
) -> EvaluateDelta:
    return EvaluateDelta(
        ingestion=ingestion if ingestion is not None else _Ingestion(),
        extractor=extractor if extractor is not None else _Extractor(),
        grounding=grounding if grounding is not None else _Grounding(),
        research=research if research is not None else _Research(),
        lore=lore if lore is not None else _LoreStore(),
        tracker=tracker if tracker is not None else _TrackerStore(),
        continuity=continuity if continuity is not None else _Continuity(),
        notifier=notifier if notifier is not None else _Notifier(),
    )


def _client(
    analyze_script: Any = None,
    evaluate_delta: Any = None,
    list_tracker_items: Any = None,
    resolve_finding: Any = None,
    answer_project_question: Any = None,
) -> FlaskClient:
    app = Flask(__name__)
    app.register_blueprint(
        create_blueprint(
            cast(AnalyzeScript, analyze_script)
            if analyze_script is not None
            else _analyze_script(),
            cast(EvaluateDelta, evaluate_delta)
            if evaluate_delta is not None
            else _evaluate_delta(),
            cast(ListTrackerItems, list_tracker_items)
            if list_tracker_items is not None
            else ListTrackerItems(_TrackerStore()),
            cast(ResolveFinding, resolve_finding)
            if resolve_finding is not None
            else ResolveFinding(_TrackerStore(), _Notifier()),
            cast(AnswerProjectQuestion, answer_project_question)
            if answer_project_question is not None
            else AnswerProjectQuestion(_LoreStore(), _Grounding(), _TrackerStore()),
        )
    )
    return app.test_client()


# `project_id` is a path segment since the REST rename, so it is no longer a
# field of the body. `_SCRIPTS` is the collection it names.
_SCRIPTS = "/api/projects/proj-1/scripts"
_QUESTIONS = "/api/projects/proj-1/questions"

_ANALYZE_BODY: dict[str, Any] = {
    "jurisdiction_code": "MX",
    "gcs_uri": "gs://bucket/v1.pdf",
    "version": 1,
}


# ---------------------------------------------------------------------------
# Factory and route inventory
# ---------------------------------------------------------------------------


def test_create_blueprint_returns_a_flask_blueprint() -> None:
    from flask import Blueprint

    bp = create_blueprint(
        _analyze_script(),
        _evaluate_delta(),
        ListTrackerItems(_TrackerStore()),
        ResolveFinding(_TrackerStore(), _Notifier()),
        AnswerProjectQuestion(_LoreStore(), _Grounding(), _TrackerStore()),
    )
    assert isinstance(bp, Blueprint)


def test_blueprint_registers_exactly_the_five_demo_routes() -> None:
    app = Flask(__name__)
    app.register_blueprint(
        create_blueprint(
            _analyze_script(),
            _evaluate_delta(),
            ListTrackerItems(_TrackerStore()),
            ResolveFinding(_TrackerStore(), _Notifier()),
            AnswerProjectQuestion(_LoreStore(), _Grounding(), _TrackerStore()),
        )
    )
    routes = {
        (rule.rule, method)
        for rule in app.url_map.iter_rules()
        if rule.endpoint != "static"
        for method in rule.methods or set()
        if method not in {"HEAD", "OPTIONS"}
    }
    assert routes == {
        ("/api/projects/<project_id>/scripts", "POST"),
        ("/api/projects/<project_id>/tracker-items", "GET"),
        ("/api/tracker-items/<item_id>", "PATCH"),
        ("/api/tracker-items/<item_id>/actions", "POST"),
        ("/api/projects/<project_id>/questions", "POST"),
    }


def test_routes_module_imports_nothing_from_clearcut_adapters() -> None:
    """CP-030's layer-boundary gate makes `composition.py` the only module
    under `src/clearcut/` importing `clearcut.adapters` (D23). A route that
    named `TrackerItemNotFound` directly would break it."""
    tree = ast.parse(ROUTES_PATH.read_text())
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.append(node.module)
    violations = [
        name
        for name in names
        if name == "clearcut.adapters" or name.startswith("clearcut.adapters.")
    ]
    assert violations == []


# ---------------------------------------------------------------------------
# POST /api/analyze
# ---------------------------------------------------------------------------


def test_analyze_happy_path_returns_the_full_report_body() -> None:
    client = _client()

    response = client.post(_SCRIPTS, json=_ANALYZE_BODY)

    assert response.status_code == 200
    assert response.content_type == "application/json"
    body = response.get_json()
    assert body["gcs_uri"] == _ANALYZE_BODY["gcs_uri"]
    assert body["jurisdiction_code"] == "MX"
    assert body["project_id"] == "proj-1"
    assert len(body["findings"]) == 1
    assert "citations" in body["findings"][0]
    assert len(body["tracker_items"]) == 1
    assert body["tracker_items"][0]["state"] == "BLOCKED"


def test_analyze_response_version_is_the_one_the_use_case_reports() -> None:
    """D33: the response's `version` echoes `AnalysisReport.script.version`,
    not a hardcoded 1. Posts `version: 1` (the `AnalyzeScript` branch, CP-041)
    and substitutes a fake use case reporting a different version, so the
    assertion is about the serializer honestly reflecting the report rather
    than about which branch a given request number selects."""
    client = _client(analyze_script=_RecordingUseCase(_report(version=3)))

    response = client.post(_SCRIPTS, json={**_ANALYZE_BODY, "version": 1})

    assert response.get_json()["version"] == 3


def test_analyze_mints_a_different_script_id_on_each_call() -> None:
    client = _client()

    first = client.post(_SCRIPTS, json=_ANALYZE_BODY).get_json()
    second = client.post(_SCRIPTS, json=_ANALYZE_BODY).get_json()

    assert first["script_id"] != second["script_id"]


def test_analyze_ignores_a_client_supplied_script_id() -> None:
    client = _client()

    response = client.post(_SCRIPTS, json={**_ANALYZE_BODY, "script_id": "hacker-supplied"})

    assert response.get_json()["script_id"] != "hacker-supplied"


def test_analyze_ignores_a_client_supplied_clock_value() -> None:
    """`at` is read from the clock, never from the request body -- the
    tracker item's `updated_at` must not echo a client-supplied one."""
    client = _client()

    response = client.post(_SCRIPTS, json={**_ANALYZE_BODY, "at": "1999-01-01T00:00:00Z"})

    assert response.get_json()["tracker_items"][0]["updated_at"] != "1999-01-01T00:00:00Z"


def test_analyze_without_gcs_uri_returns_400_and_calls_no_adapter() -> None:
    ingestion = _Ingestion()
    client = _client(analyze_script=_analyze_script(ingestion=ingestion))
    body = {k: v for k, v in _ANALYZE_BODY.items() if k != "gcs_uri"}

    response = client.post(_SCRIPTS, json=body)

    assert response.status_code == 400
    assert "gcs_uri" in response.get_json()["error"]
    assert ingestion.calls == []


@pytest.mark.parametrize("bad_version", [None, "1", 0, -1, True])
def test_analyze_with_an_invalid_version_returns_400_and_calls_no_adapter(bad_version: Any) -> None:
    ingestion = _Ingestion()
    client = _client(analyze_script=_analyze_script(ingestion=ingestion))
    body = dict(_ANALYZE_BODY)
    if bad_version is None:
        del body["version"]
    else:
        body["version"] = bad_version

    response = client.post(_SCRIPTS, json=body)

    assert response.status_code == 400
    assert "version" in response.get_json()["error"]
    assert ingestion.calls == []


def test_analyze_with_an_unknown_jurisdiction_code_returns_400_naming_it() -> None:
    client = _client()

    response = client.post(_SCRIPTS, json={**_ANALYZE_BODY, "jurisdiction_code": "ZZ"})

    assert response.status_code == 400
    assert "ZZ" in response.get_json()["error"]


def test_analyze_maps_record_not_found_to_404() -> None:
    client = _client(analyze_script=_RaisingUseCase(RecordNotFound("no such record")))

    response = client.post(_SCRIPTS, json=_ANALYZE_BODY)

    assert response.status_code == 404
    assert response.content_type == "application/json"
    assert "no such record" in response.get_json()["error"]


def test_analyze_maps_source_unavailable_to_502() -> None:
    client = _client(analyze_script=_RaisingUseCase(SourceUnavailable("upstream down")))

    response = client.post(_SCRIPTS, json=_ANALYZE_BODY)

    assert response.status_code == 502
    assert "upstream down" in response.get_json()["error"]


def test_analyze_maps_an_unmapped_type_error_to_500_with_no_internals_leaked() -> None:
    client = _client(analyze_script=_RaisingUseCase(TypeError("boom: secret internals")))

    response = client.post(_SCRIPTS, json=_ANALYZE_BODY)

    assert response.status_code == 500
    assert response.content_type == "application/json"
    body = response.get_json()
    assert "secret internals" not in body["error"]
    assert "Traceback" not in body["error"]


def test_analyze_maps_a_bare_value_error_to_500() -> None:
    """D27: two adapter guards still raise a bare `ValueError` across a
    port. Unreachable from a validated request, so a 500 is the honest
    answer rather than a Flask traceback."""
    client = _client(analyze_script=_RaisingUseCase(ValueError("blank corpus_prefix")))

    response = client.post(_SCRIPTS, json=_ANALYZE_BODY)

    assert response.status_code == 500
    assert "blank corpus_prefix" not in response.get_json()["error"]


# ---------------------------------------------------------------------------
# POST /api/analyze -- version routing (CP-041, D30)
# ---------------------------------------------------------------------------


def test_analyze_with_version_1_calls_analyze_script_and_not_evaluate_delta() -> None:
    analyze_script = _RecordingUseCase(_report(version=1))
    evaluate_delta = _RecordingUseCase(_report(version=1))
    client = _client(analyze_script=analyze_script, evaluate_delta=evaluate_delta)

    response = client.post(_SCRIPTS, json={**_ANALYZE_BODY, "version": 1})

    assert response.status_code == 200
    assert len(analyze_script.calls) == 1
    assert analyze_script.calls[0][2] == 1
    assert evaluate_delta.calls == []


def test_analyze_with_version_greater_than_1_calls_evaluate_delta_and_not_analyze_script() -> None:
    analyze_script = _RecordingUseCase(_report(version=2))
    evaluate_delta = _RecordingUseCase(_report(version=2))
    client = _client(analyze_script=analyze_script, evaluate_delta=evaluate_delta)

    response = client.post(_SCRIPTS, json={**_ANALYZE_BODY, "version": 2})

    assert response.status_code == 200
    assert len(evaluate_delta.calls) == 1
    assert evaluate_delta.calls[0][2] == 2
    assert analyze_script.calls == []


def test_delta_response_carries_the_same_keys_as_the_analyze_response() -> None:
    """D30's second half: one route, one response shape, so the SPA renders
    both paths from a single client shape. `latest_script` returns a
    previous version whose only scene is unchanged, so the delta run has
    nothing to re-extract -- the branch under test is which use case
    answers, not what it finds."""
    previous = Script(
        script_id="scr-0",
        project_id="proj-1",
        version=1,
        gcs_uri="gs://bucket/v1.pdf",
        jurisdiction_code="MX",
        scenes=[_scene()],
    )
    client = _client(
        evaluate_delta=_evaluate_delta(tracker=_TrackerStore(previous_script=previous))
    )

    analyze_response = client.post(_SCRIPTS, json=_ANALYZE_BODY)
    delta_response = client.post(_SCRIPTS, json={**_ANALYZE_BODY, "version": 2})

    assert analyze_response.status_code == 200
    assert delta_response.status_code == 200
    assert set(delta_response.get_json().keys()) == set(analyze_response.get_json().keys())


def test_analyze_version_2_with_no_previous_version_returns_404_naming_the_project() -> None:
    client = _client(evaluate_delta=_evaluate_delta())

    response = client.post(_SCRIPTS, json={**_ANALYZE_BODY, "version": 2})

    assert response.status_code == 404
    assert response.content_type == "application/json"
    assert "proj-1" in response.get_json()["error"]


@pytest.mark.parametrize("bad_version", [None, "2", 0])
def test_analyze_with_an_invalid_version_calls_neither_use_case(bad_version: Any) -> None:
    analyze_script = _RecordingUseCase(_report())
    evaluate_delta = _RecordingUseCase(_report())
    client = _client(analyze_script=analyze_script, evaluate_delta=evaluate_delta)
    body = dict(_ANALYZE_BODY)
    if bad_version is None:
        del body["version"]
    else:
        body["version"] = bad_version

    response = client.post(_SCRIPTS, json=body)

    assert response.status_code == 400
    assert analyze_script.calls == []
    assert evaluate_delta.calls == []


# ---------------------------------------------------------------------------
# POST /api/analyze -- scenes in the response body (CP-047)
# ---------------------------------------------------------------------------


def _expected_scene_json(scene: Scene) -> dict[str, Any]:
    return {
        "number": scene.number,
        "heading": scene.heading,
        "page_start": scene.page_start,
        "page_end": scene.page_end,
        "text": scene.text,
        "content_hash": scene.content_hash,
    }


def test_analyze_response_scenes_match_the_report_field_for_field_in_order() -> None:
    scenes = [
        Scene(
            number=1,
            heading="INT. BAR - DAY",
            page_start=1,
            page_end=1,
            text="A neon Quilmes sign glows.",
        ),
        Scene(
            number=2,
            heading="EXT. STREET - NIGHT",
            page_start=2,
            page_end=3,
            text="Rain on cobblestones.",
        ),
    ]
    report = AnalysisReport(
        script=Script(
            script_id="scr-1",
            project_id="proj-1",
            version=1,
            gcs_uri="gs://bucket/v1.pdf",
            jurisdiction_code="MX",
            scenes=scenes,
        ),
        findings=(),
        tracker_items=(),
    )
    client = _client(analyze_script=_RecordingUseCase(report))

    response = client.post(_SCRIPTS, json=_ANALYZE_BODY)

    assert response.get_json()["scenes"] == [_expected_scene_json(scene) for scene in scenes]


def test_analyze_response_scene_content_hash_is_the_domains_own_hash() -> None:
    """The adapter reads `scene.content_hash`, never recomputes it -- the
    hash is the domain's (AGENT.md Section 3, Information Expert)."""
    scene = _scene()
    report = AnalysisReport(
        script=Script(
            script_id="scr-1",
            project_id="proj-1",
            version=1,
            gcs_uri="gs://bucket/v1.pdf",
            jurisdiction_code="MX",
            scenes=[scene],
        ),
        findings=(),
        tracker_items=(),
    )
    client = _client(analyze_script=_RecordingUseCase(report))

    response = client.post(_SCRIPTS, json=_ANALYZE_BODY)

    returned_hash = response.get_json()["scenes"][0]["content_hash"]
    assert returned_hash == scene.content_hash
    assert returned_hash != ""


def test_delta_response_scenes_are_the_newly_parsed_version_not_the_previous_one() -> None:
    """`EvaluateDelta.execute` builds `Script(scenes=scenes, ...)` from the
    scenes it just parsed, never from `tracker.latest_script`'s stored
    previous version (application/evaluate_delta.py)."""
    previous = Script(
        script_id="scr-0",
        project_id="proj-1",
        version=1,
        gcs_uri="gs://bucket/v1.pdf",
        jurisdiction_code="MX",
        scenes=[_scene(number=1)],
    )
    new_scenes = [_scene(number=1), _scene(number=2)]
    client = _client(
        evaluate_delta=_evaluate_delta(
            ingestion=_Ingestion(scenes=new_scenes),
            tracker=_TrackerStore(previous_script=previous),
        )
    )

    response = client.post(_SCRIPTS, json={**_ANALYZE_BODY, "version": 2})

    assert [scene["number"] for scene in response.get_json()["scenes"]] == [1, 2]


def test_analyze_response_key_set_is_exactly_eight_keys() -> None:
    client = _client()

    response = client.post(_SCRIPTS, json=_ANALYZE_BODY)

    assert set(response.get_json().keys()) == {
        "script_id",
        "project_id",
        "version",
        "gcs_uri",
        "jurisdiction_code",
        "scenes",
        "findings",
        "tracker_items",
    }


def test_analyze_response_scenes_is_an_empty_list_never_null_for_a_script_with_no_scenes() -> None:
    client = _client(analyze_script=_RecordingUseCase(_report()))

    response = client.post(_SCRIPTS, json=_ANALYZE_BODY)

    assert response.get_json()["scenes"] == []


# ---------------------------------------------------------------------------
# GET /api/tracker
# ---------------------------------------------------------------------------


def test_tracker_list_happy_path_returns_only_the_named_projects_items() -> None:
    tracker = _TrackerStore([_item("itm-1", "proj-1"), _item("itm-2", "proj-2")])
    client = _client(list_tracker_items=ListTrackerItems(tracker))

    response = client.get("/api/projects/proj-1/tracker-items")

    assert response.status_code == 200
    body = response.get_json()
    assert len(body) == 1
    assert body[0]["item_id"] == "itm-1"


def test_tracker_list_without_a_project_in_the_path_is_not_routed() -> None:
    tracker = _TrackerStore()
    client = _client(list_tracker_items=ListTrackerItems(tracker))

    # The check moved into routing rather than disappearing. `project_id` is a
    # path segment now, so a URL that names no project matches no rule and
    # Flask answers 404 before any handler runs -- which is still "no adapter
    # was called", proved the same way below.
    response = client.get("/api/projects//tracker-items")

    assert response.status_code == 404
    assert tracker.latest_for_project_calls == []


def test_tracker_list_maps_source_unavailable_to_502() -> None:
    client = _client(list_tracker_items=_RaisingUseCase(SourceUnavailable("clickhouse down")))

    response = client.get("/api/projects/proj-1/tracker-items")

    assert response.status_code == 502


# ---------------------------------------------------------------------------
# PATCH /api/tracker/<item_id>
# ---------------------------------------------------------------------------


def test_tracker_patch_happy_path_transitions_the_item() -> None:
    tracker = _TrackerStore([_item("itm-1")])
    client = _client(resolve_finding=ResolveFinding(tracker, _Notifier()))

    response = client.patch("/api/tracker-items/itm-1", json={"state": "IN_PROGRESS"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["state"] == "IN_PROGRESS"
    assert body["version"] == 2


def test_tracker_patch_with_an_invalid_state_returns_400_naming_accepted_values() -> None:
    tracker = _TrackerStore([_item("itm-1")])
    client = _client(resolve_finding=ResolveFinding(tracker, _Notifier()))

    response = client.patch("/api/tracker-items/itm-1", json={"state": "DELETED"})

    assert response.status_code == 400
    error = response.get_json()["error"]
    assert "BLOCKED" in error and "IN_PROGRESS" in error and "CLEARED" in error
    assert tracker.latest_calls == []


def test_tracker_patch_maps_record_not_found_to_404() -> None:
    tracker = _TrackerStore([])
    client = _client(resolve_finding=ResolveFinding(tracker, _Notifier()))

    response = client.patch("/api/tracker-items/missing-item", json={"state": "IN_PROGRESS"})

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/tracker/<item_id>/actions
# ---------------------------------------------------------------------------


def test_tracker_actions_draft_email_happy_path() -> None:
    tracker = _TrackerStore([_item("itm-1")])
    client = _client(resolve_finding=ResolveFinding(tracker, _Notifier()))

    response = client.post("/api/tracker-items/itm-1/actions", json={"action": "draft_email"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["draft_email"] is not None
    assert body["version"] == 2


def test_tracker_actions_notify_happy_path_calls_notifier_and_leaves_item_unchanged() -> None:
    tracker = _TrackerStore([_item("itm-1")])
    notifier = _Notifier()
    client = _client(resolve_finding=ResolveFinding(tracker, notifier))

    response = client.post(
        "/api/tracker-items/itm-1/actions", json={"action": "notify", "reason": "please respond"}
    )

    assert response.status_code == 200
    assert response.get_json()["version"] == 1
    assert len(notifier.calls) == 1
    assert notifier.calls[0][1] == "please respond"


def test_tracker_actions_notify_failure_maps_notification_failed_to_502() -> None:
    """D28: `notify` writes nothing, so a `SourceUnavailable`-family failure
    (the shape `NotificationFailed` takes, D23) is the whole request's
    outcome. A 502 reports it truthfully."""
    tracker = _TrackerStore([_item("itm-1")])
    client = _client(resolve_finding=_RaisingUseCase(SourceUnavailable("webhook unreachable")))

    response = client.post("/api/tracker-items/itm-1/actions", json={"action": "notify"})

    assert response.status_code == 502
    assert tracker.saved == []


def test_tracker_actions_with_an_unsupported_action_returns_500_with_no_internals_leaked() -> None:
    tracker = _TrackerStore([_item("itm-1")])
    client = _client(resolve_finding=ResolveFinding(tracker, _Notifier()))

    response = client.post("/api/tracker-items/itm-1/actions", json={"action": "stakeholder_link"})

    assert response.status_code == 500
    assert response.content_type == "application/json"
    assert tracker.saved == []


# ---------------------------------------------------------------------------
# POST /api/question
# ---------------------------------------------------------------------------


def test_question_happy_path_returns_an_answer_body() -> None:
    """Pins the request-to-use-case binding (routes.py:285-287), not just the
    body's shape: the recorded `LoreStore.search` call carries this request's
    own `project_id` and question, the resolved (not a hardcoded)
    `Jurisdiction` reaches `LegalGrounding.ground`, and the body's `text` is
    the use case's composed answer rather than a constant. A question naming
    a legal topic ("license") is used so grounding is actually exercised,
    without also naming a blocker word."""
    lore = _LoreStore()
    grounding = _Grounding(GroundedAnswer(text="MX requires a music sync license.", citations=()))
    client = _client(
        answer_project_question=AnswerProjectQuestion(lore, grounding, _TrackerStore())
    )
    question_text = "does this need a music license?"

    response = client.post(
        _QUESTIONS,
        json={"project_id": "proj-1", "question": question_text, "jurisdiction_code": "MX"},
    )

    assert response.status_code == 200
    assert len(lore.searched) == 1
    searched_project_id, searched_question, _limit = lore.searched[0]
    assert searched_project_id == "proj-1"
    assert searched_question == question_text
    assert grounding.calls == [(question_text, _MEXICO)]
    body = response.get_json()
    assert body["text"] == "MX requires a music sync license."
    assert body["facts"] == []
    assert body["citations"] == []


def test_a_question_with_no_project_in_the_path_is_not_routed() -> None:
    """The blank-project_id 400 became a routing concern.

    `project_id` used to be a body field this handler validated. It is a path
    segment now, so a URL naming no project matches no rule and never reaches
    the handler -- the guarantee that mattered, that no adapter is called, is
    unchanged and still asserted.
    """
    lore = _LoreStore()
    client = _client(
        answer_project_question=AnswerProjectQuestion(lore, _Grounding(), _TrackerStore())
    )

    response = client.post("/api/projects//questions", json={"question": "what is blocked?"})

    assert response.status_code == 404
    assert lore.searched == []


def test_question_with_an_unknown_jurisdiction_code_returns_400_naming_it() -> None:
    client = _client()

    response = client.post(
        _QUESTIONS,
        json={"project_id": "proj-1", "question": "what is blocked?", "jurisdiction_code": "ZZ"},
    )

    assert response.status_code == 400
    assert "ZZ" in response.get_json()["error"]


def test_question_maps_source_unavailable_to_502() -> None:
    client = _client(
        answer_project_question=_RaisingUseCase(SourceUnavailable("vertex search down"))
    )

    response = client.post(
        _QUESTIONS,
        json={"project_id": "proj-1", "question": "what is blocked?", "jurisdiction_code": "MX"},
    )

    assert response.status_code == 502
