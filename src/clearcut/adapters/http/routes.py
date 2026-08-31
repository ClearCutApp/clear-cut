"""Maps the five demo-path HTTP routes onto the use cases (docs/plan/sdd.md
Section 4.2; AGENT.md Section 2 -- "the route only maps HTTP to use-case
input/output, and holds no orchestration").

`create_blueprint` takes use-case instances only, never a port: a route that
held `TrackerStore` would be the same orchestration mistake CHECKPOINTS.md
Decision D30 ruled out for the script-recording write ("CP-029's factory
takes use-case instances and nothing else"), and it would break the
single-importer rule CP-030's layer-boundary gate enforces on
`clearcut.adapters` -- this module names only `clearcut.application` and
`clearcut.domain`, never a sibling `clearcut.adapters` package or one of its
error classes (Decision D23).

Every unmapped exception becomes a JSON 500 with no stack trace: that is
this module's own edge-of-the-system catch, not a violation of the
`application/`-only bare-except guard in `tests/unit/test_error_boundaries.py`
(that guard scopes to `application/`, not `adapters/`).
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from flask import Blueprint, jsonify, request
from flask.typing import ResponseReturnValue

from clearcut.application.analyze_script import AnalysisReport, AnalyzeScript
from clearcut.application.answer_project_question import AnswerProjectQuestion, ProjectAnswer
from clearcut.application.evaluate_delta import EvaluateDelta
from clearcut.application.list_tracker_items import ListTrackerItems
from clearcut.application.resolve_finding import (
    Action,
    DraftEmail,
    Notify,
    ResolveFinding,
    Transition,
)
from clearcut.domain.bible import BibleFact
from clearcut.domain.errors import RecordNotFound, SourceUnavailable, UnknownJurisdiction
from clearcut.domain.finding import Citation, Finding
from clearcut.domain.jurisdiction import Jurisdiction, jurisdiction_for
from clearcut.domain.tracker import TrackerItem, TrackerState

_ACCEPTED_STATES = tuple(state.value for state in TrackerState)

JsonDict = dict[str, Any]


def _new_script_id() -> str:
    return uuid.uuid4().hex


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_body() -> JsonDict:
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def _error_response(status: int, message: str) -> ResponseReturnValue:
    return jsonify({"error": message}), status


def _run_use_case(build_response: Callable[[], JsonDict | list[JsonDict]]) -> ResponseReturnValue:
    """Calls `build_response` and maps whatever it raises to a status code.

    `build_response` both calls the use case and serializes its result, so a
    caught error can never be a serialization bug wearing a 404's clothes.
    """
    try:
        return jsonify(build_response())
    except RecordNotFound as error:
        return _error_response(404, str(error))
    except SourceUnavailable as error:
        return _error_response(502, str(error))
    except Exception:
        # Neither of the two mapped domain errors, and not `EnrichmentMissing`
        # either -- that one is caught inside the use case and never reaches
        # here (D23). Includes the bare `ValueError` two adapter guards still
        # raise across a port; both are unreachable from a validated request
        # (D27), so a 500 with no stack trace is the honest answer.
        return _error_response(500, "internal error")


def _require_field(body: JsonDict, field: str) -> str | ResponseReturnValue:
    """The stripped string at `body[field]`, or a 400 naming `field`."""
    value = body.get(field)
    if not isinstance(value, str) or not value.strip():
        return _error_response(400, f"{field} is required")
    return value


def _require_version(body: JsonDict) -> int | ResponseReturnValue:
    value = body.get("version")
    # `bool` is a subclass of `int`; `version: true` must not read as 1.
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return _error_response(400, "version must be an integer >= 1")
    return value


def _require_state(body: JsonDict) -> TrackerState | ResponseReturnValue:
    value = body.get("state")
    if value not in _ACCEPTED_STATES:
        return _error_response(400, f"state must be one of: {', '.join(_ACCEPTED_STATES)}")
    return TrackerState(value)


def _build_action(body: JsonDict) -> Action:
    raw = body.get("action")
    if raw == "draft_email":
        return DraftEmail()
    if raw == "notify":
        return Notify(reason=str(body.get("reason", "")))
    # `generate_document` and `stakeholder_link` (SDD Section 4.2) are not
    # implemented -- `ResolveFinding` (CP-025) is scoped to three actions.
    # Unreachable from the deployed SPA, and `_run_use_case`'s generic catch
    # turns it into a 500 rather than a lie about what happened.
    raise ValueError(f"unsupported action: {raw!r}")


def _citation_json(citation: Citation) -> JsonDict:
    return {"uri": citation.uri, "title": citation.title, "snippet": citation.snippet}


def _finding_json(finding: Finding) -> JsonDict:
    return {
        "finding_id": finding.finding_id,
        "scene_number": finding.scene_number,
        "page": finding.page,
        "raw_text": finding.raw_text,
        "category": finding.category.value,
        "ner_label": finding.ner_label.value if finding.ner_label is not None else None,
        "risk_level": finding.risk_level.value,
        "required_document": finding.required_document,
        "citations": [_citation_json(citation) for citation in finding.citations],
        "contradicts": finding.contradicts,
    }


def _tracker_item_json(item: TrackerItem) -> JsonDict:
    return {
        "item_id": item.item_id,
        "project_id": item.project_id,
        "finding_id": item.finding_id,
        "scene_numbers": list(item.scene_numbers),
        "state": item.state.value,
        "needs_review": item.needs_review,
        "required_document": item.required_document,
        "contact": item.contact,
        "litigation_posture": item.litigation_posture,
        "draft_email": item.draft_email,
        "note": item.note,
        "updated_at": item.updated_at,
        "version": item.version,
    }


def _analysis_report_json(report: AnalysisReport) -> JsonDict:
    script = report.script
    return {
        "script_id": script.script_id,
        "project_id": script.project_id,
        "version": script.version,
        "gcs_uri": script.gcs_uri,
        "jurisdiction_code": script.jurisdiction_code,
        "findings": [_finding_json(finding) for finding in report.findings],
        "tracker_items": [_tracker_item_json(item) for item in report.tracker_items],
    }


def _bible_fact_json(fact: BibleFact) -> JsonDict:
    return {
        "fact_id": fact.fact_id,
        "kind": fact.kind.value,
        "text": fact.text,
        "source": fact.source,
    }


def _project_answer_json(answer: ProjectAnswer) -> JsonDict:
    return {
        "text": answer.text,
        "facts": [_bible_fact_json(fact) for fact in answer.facts],
        "citations": [_citation_json(citation) for citation in answer.citations],
    }


def _resolve_jurisdiction(code: str) -> Jurisdiction | ResponseReturnValue:
    """A `Jurisdiction`, or a 400 `ResponseReturnValue` naming `code`.

    Same early-return-on-error shape every other `_require_*` helper in this
    module uses, checked with `isinstance(result, Jurisdiction)`.
    """
    try:
        return jurisdiction_for(code)
    except UnknownJurisdiction as error:
        return _error_response(400, str(error))


def create_blueprint(
    analyze_script: AnalyzeScript,
    evaluate_delta: EvaluateDelta,
    list_tracker_items: ListTrackerItems,
    resolve_finding: ResolveFinding,
    answer_project_question: AnswerProjectQuestion,
) -> Blueprint:
    """The five demo-path routes (SDD Section 4.2), as a Flask blueprint over
    the five use-case instances the caller (`composition.py`) built."""
    bp = Blueprint("clearcut_api", __name__)

    @bp.route("/api/analyze", methods=["POST"])
    def analyze() -> ResponseReturnValue:
        body = _json_body()
        gcs_uri = _require_field(body, "gcs_uri")
        if not isinstance(gcs_uri, str):
            return gcs_uri
        version = _require_version(body)
        if not isinstance(version, int):
            return version
        jurisdiction = _resolve_jurisdiction(str(body.get("jurisdiction_code", "")))
        if not isinstance(jurisdiction, Jurisdiction):
            return jurisdiction
        project_id = str(body.get("project_id", ""))
        script_id = _new_script_id()
        at = _now()

        def build() -> JsonDict:
            # version 1 is a first upload; version > 1 diffs against the
            # stored previous one (D30). `EvaluateDelta.execute` shares
            # `AnalyzeScript.execute`'s exact signature and return shape, so
            # one call site and one serializer (`_analysis_report_json`)
            # cover both branches.
            use_case = analyze_script if version == 1 else evaluate_delta
            report = use_case.execute(project_id, script_id, version, gcs_uri, jurisdiction, at)
            return _analysis_report_json(report)

        return _run_use_case(build)

    @bp.route("/api/tracker", methods=["GET"])
    def tracker_list() -> ResponseReturnValue:
        project_id = request.args.get("project_id")
        if not project_id or not project_id.strip():
            return _error_response(400, "project_id is required")

        def build() -> list[JsonDict]:
            items = list_tracker_items.execute(project_id)
            return [_tracker_item_json(item) for item in items]

        return _run_use_case(build)

    @bp.route("/api/tracker/<item_id>", methods=["PATCH"])
    def tracker_patch(item_id: str) -> ResponseReturnValue:
        body = _json_body()
        state = _require_state(body)
        if not isinstance(state, TrackerState):
            return state
        at = _now()

        def build() -> JsonDict:
            item = resolve_finding.execute(item_id, Transition(state), at)
            return _tracker_item_json(item)

        return _run_use_case(build)

    @bp.route("/api/tracker/<item_id>/actions", methods=["POST"])
    def tracker_actions(item_id: str) -> ResponseReturnValue:
        body = _json_body()
        at = _now()

        def build() -> JsonDict:
            action = _build_action(body)
            item = resolve_finding.execute(item_id, action, at)
            return _tracker_item_json(item)

        return _run_use_case(build)

    @bp.route("/api/question", methods=["POST"])
    def question() -> ResponseReturnValue:
        body = _json_body()
        project_id = _require_field(body, "project_id")
        if not isinstance(project_id, str):
            return project_id
        jurisdiction = _resolve_jurisdiction(str(body.get("jurisdiction_code", "")))
        if not isinstance(jurisdiction, Jurisdiction):
            return jurisdiction
        question_text = str(body.get("question", ""))

        def build() -> JsonDict:
            answer = answer_project_question.execute(project_id, question_text, jurisdiction)
            return _project_answer_json(answer)

        return _run_use_case(build)

    return bp
