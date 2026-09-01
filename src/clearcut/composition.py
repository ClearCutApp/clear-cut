"""The single wiring point (AGENT.md Section 2 rule 4): `create_app()` is the
Cloud Run entry point `gcloud run deploy --source .` starts.

`CLEARCUT_MODE` selects the wiring (CHECKPOINTS.md Decision D36): `mock`
builds CP-043's in-memory demo adapters over the SDD Section 8(d) scenario and
reads no credential at all; `live` delegates to the eight-adapter graph
CP-049 fills, the seam Decision D38 chose (a plain constructor argument with a
real, eager-connecting default, not a lazy wrapper). An absent variable means
`live`, so a deployment that forgot to set it never serves planted data
instead of a loud startup failure. An unrecognized value is fatal at startup
too, naming the variable and both accepted values -- the fallback nobody
notices is the one that ships.

One `if`, one wiring function per branch, the same route factory
(`create_blueprint`, CP-029) below both -- plain constructor injection, no DI
container, no service locator, no module-level singleton, no registry (AGENT.md
Section 4). Nothing is built at import time: two `create_app()` calls each
build a fresh `_UseCaseGraph`, so they never share state.
"""

import logging
import os
from dataclasses import dataclass

from flask import Flask

from clearcut.adapters.demo.in_memory import (
    InMemoryContinuityCheck,
    InMemoryLegalGrounding,
    InMemoryLoreStore,
    InMemoryNotifier,
    InMemoryRightsResearch,
    InMemorySceneExtractor,
    InMemoryScriptIngestion,
    InMemoryTrackerStore,
)
from clearcut.adapters.http.routes import create_blueprint
from clearcut.application.analyze_script import AnalyzeScript
from clearcut.application.answer_project_question import AnswerProjectQuestion
from clearcut.application.evaluate_delta import EvaluateDelta
from clearcut.application.list_tracker_items import ListTrackerItems
from clearcut.application.resolve_finding import ResolveFinding

logger = logging.getLogger(__name__)

_MODE_ENV_VAR = "CLEARCUT_MODE"
_MOCK_MODE = "mock"
_LIVE_MODE = "live"


@dataclass(frozen=True)
class _UseCaseGraph:
    """The five use-case instances `create_blueprint` (CP-029) mounts onto
    the five demo-path routes -- one graph per mode branch, same shape."""

    analyze_script: AnalyzeScript
    evaluate_delta: EvaluateDelta
    list_tracker_items: ListTrackerItems
    resolve_finding: ResolveFinding
    answer_project_question: AnswerProjectQuestion


def _build_mock_use_cases() -> _UseCaseGraph:
    """Wires CP-043's demo adapters into the five use cases: no credential
    read, no vendor client built, no socket opened. `lore`, `tracker`, and
    `notifier` are shared across use cases so a write from one route (a
    `POST /api/analyze`) is visible to another (a `GET /api/tracker`)."""
    ingestion = InMemoryScriptIngestion()
    extractor = InMemorySceneExtractor()
    grounding = InMemoryLegalGrounding()
    research = InMemoryRightsResearch()
    continuity = InMemoryContinuityCheck()
    lore = InMemoryLoreStore()
    tracker = InMemoryTrackerStore()
    notifier = InMemoryNotifier()
    return _UseCaseGraph(
        analyze_script=AnalyzeScript(
            ingestion, extractor, grounding, research, lore, tracker, continuity
        ),
        evaluate_delta=EvaluateDelta(
            ingestion, extractor, grounding, research, lore, tracker, continuity, notifier
        ),
        list_tracker_items=ListTrackerItems(tracker),
        resolve_finding=ResolveFinding(tracker, notifier),
        answer_project_question=AnswerProjectQuestion(lore, grounding, tracker),
    )


def _build_live_use_cases() -> _UseCaseGraph:
    """The live wiring seam CP-049 fills (Decision D38): the eight live
    adapters, built from environment-read credentials, with the two
    connecting vendor clients accepted as constructor arguments with real
    defaults. Raising here -- rather than returning a half-wired graph --
    keeps `CLEARCUT_MODE=live` from ever silently falling back to mock."""
    raise RuntimeError(
        "CLEARCUT_MODE=live wiring is incomplete: CP-049 has not wired the eight live adapters yet"
    )


def create_app() -> Flask:
    """The Cloud Run entry point. Builds a fresh `_UseCaseGraph` per call and
    mounts it through CP-029's frozen five-argument `create_blueprint`."""
    mode = os.environ.get(_MODE_ENV_VAR, _LIVE_MODE)
    if mode == _MOCK_MODE:
        logger.warning(
            "CLEARCUT_MODE=mock: serving the planted demo scenario, no live service is connected"
        )
        use_cases = _build_mock_use_cases()
    elif mode == _LIVE_MODE:
        use_cases = _build_live_use_cases()
    else:
        raise ValueError(
            f"{_MODE_ENV_VAR}={mode!r} is not recognized; set it to "
            f"{_MOCK_MODE!r} or {_LIVE_MODE!r}"
        )

    app = Flask(__name__)
    app.register_blueprint(
        create_blueprint(
            use_cases.analyze_script,
            use_cases.evaluate_delta,
            use_cases.list_tracker_items,
            use_cases.resolve_finding,
            use_cases.answer_project_question,
        )
    )
    return app
