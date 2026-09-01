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
from pathlib import Path

from flask import Flask
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

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
from clearcut.adapters.http.spa import create_spa_blueprint
from clearcut.application.analyze_script import AnalyzeScript
from clearcut.application.answer_project_question import AnswerProjectQuestion
from clearcut.application.evaluate_delta import EvaluateDelta
from clearcut.application.list_tracker_items import ListTrackerItems
from clearcut.application.resolve_finding import ResolveFinding

logger = logging.getLogger(__name__)

_MODE_ENV_VAR = "CLEARCUT_MODE"
_MOCK_MODE = "mock"
_LIVE_MODE = "live"

_OTEL_ENDPOINT_ENV_VAR = "OTEL_EXPORTER_OTLP_ENDPOINT"


def _span_exporter() -> OTLPSpanExporter | None:
    """The trace half of the OTLP exporter ADR 0008 sends to Grafana Cloud,
    or `None` when `OTEL_EXPORTER_OTLP_ENDPOINT` is unset (CP-031's
    unset-endpoint failure path: spans still get created, for the trace
    context every stage span propagates through, they simply go nowhere).
    Constructed with no arguments -- `OTLPSpanExporter` reads
    `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS` itself,
    the standard OTel exporter behaviour, so this module never parses either
    variable by hand."""
    if _OTEL_ENDPOINT_ENV_VAR not in os.environ:
        return None
    return OTLPSpanExporter()


def _metric_exporter() -> OTLPMetricExporter | None:
    """The metrics half of the same exporter; `None` under the same
    condition as `_span_exporter`, for the same reason."""
    if _OTEL_ENDPOINT_ENV_VAR not in os.environ:
        return None
    return OTLPMetricExporter()


def _configure_telemetry() -> None:
    """Installs the tracer and meter providers every adapter's own
    `trace.get_tracer(__name__)` / `metrics.get_meter(__name__)` call
    resolves against (ADR 0008, SDD Section 6) -- once per process, guarded
    so a second `create_app()` call (every test after the first one in the
    same process) is a no-op rather than a warning: OpenTelemetry's own
    global providers already refuse a second `set_tracer_provider` /
    `set_meter_provider` and merely log when that happens, so this check
    keeps the no-op explicit instead of leaning on that fallback."""
    if not isinstance(trace.get_tracer_provider(), trace.ProxyTracerProvider):
        return

    tracer_provider = TracerProvider()
    span_exporter = _span_exporter()
    if span_exporter is not None:
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    metric_exporter = _metric_exporter()
    metric_readers = [PeriodicExportingMetricReader(metric_exporter)] if metric_exporter else []
    metrics.set_meter_provider(MeterProvider(metric_readers=metric_readers))


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


def _default_build_dir() -> Path:
    """`web/dist`, the Vite build output ADR 0010 says this container serves
    -- computed here, inside the function, on every call, rather than as a
    module-level constant: importing this module must never touch the
    filesystem, and a test must be free to point `create_app` at any
    directory it likes instead."""
    return Path(__file__).resolve().parent.parent.parent / "web" / "dist"


def create_app(build_dir: Path | None = None) -> Flask:
    """The Cloud Run entry point. Builds a fresh `_UseCaseGraph` per call and
    mounts it through CP-029's frozen five-argument `create_blueprint`,
    alongside CP-046's SPA blueprint serving `build_dir` (default
    `web/dist`) -- one origin for the JSON API and the static build (ADR
    0010), so no CORS configuration is ever needed."""
    _configure_telemetry()
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
    app.register_blueprint(
        create_spa_blueprint(build_dir if build_dir is not None else _default_build_dir())
    )
    return app
