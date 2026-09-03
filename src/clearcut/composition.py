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
from typing import cast

import clickhouse_connect
import httpx
from flask import Flask
from google import genai
from google.cloud import documentai_v1 as documentai
from langchain_google_community import BigQueryVectorStore  # type: ignore[import-untyped]
from langchain_google_vertexai import VertexAIEmbeddings
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from clearcut.adapters.bigquery.lore_store import BigQueryLoreStore, _VectorStore
from clearcut.adapters.clickhouse.tracker import ClickHouseTrackerStore, _ChClient
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
from clearcut.adapters.gcp.document_ai import DocumentAIIngestion
from clearcut.adapters.gcp.vertex_search import VertexSearchGrounding
from clearcut.adapters.gemini.continuity import GeminiContinuityCheck
from clearcut.adapters.gemini.extractor import GeminiSceneExtractor
from clearcut.adapters.http.health import create_health_blueprint
from clearcut.adapters.http.routes import create_blueprint
from clearcut.adapters.http.spa import create_spa_blueprint
from clearcut.adapters.notify.webhook import WebhookNotifier
from clearcut.adapters.parallel.research import ParallelRightsResearch
from clearcut.application.analyze_script import AnalyzeScript
from clearcut.application.answer_project_question import AnswerProjectQuestion
from clearcut.application.evaluate_delta import EvaluateDelta
from clearcut.application.list_tracker_items import ListTrackerItems
from clearcut.application.resolve_finding import ResolveFinding

logger = logging.getLogger(__name__)

# Fixed for the hackathon's single region and dataset (docs/plan/infrastructure.md
# Sections 4 and 5); none of these has ever varied, so none is a constructor
# argument or an environment variable (AGENT.md Section 4).
_GCP_LOCATION = "us-central1"
# The Gemini 3 family answers only on the global endpoint. Probed against the
# real API on 2026-09-03 (CP-055): gemini-3.7-flash, gemini-3.1-flash-lite and
# gemini-3-flash-preview all return 404 NOT_FOUND at us-central1 with "your
# project does not have access to it", and all answer at global; the 2.5 family
# answers at both. ADR 0002 noted the global-only constraint for
# gemini-3.1-pro-preview -- it holds for the whole generation, including the two
# models that ADR pins. Kept separate from `_GCP_LOCATION` because the BigQuery
# dataset and the embeddings live in us-central1 and do not exist at global.
_GENAI_LOCATION = "global"
_BIGQUERY_DATASET = "clearcut"
_BIGQUERY_LORE_TABLE = "lore_vectors"
_EMBEDDING_MODEL = "text-embedding-005"

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


def _clickhouse_host(configured: str) -> str:
    """The bare hostname `clickhouse_connect` wants, from whatever was pasted.

    The Cloud console's Connect panel shows a full URL, and
    `get_client(host=...)` prepends the scheme itself, so pasting that value
    verbatim produces `https://https://host:8443` and fails DNS resolution on
    the literal string "https". Seen on the first real connection attempt
    (2026-09-03, CP-055).

    Normalised here rather than documented as a footnote, because the console
    is where every operator will copy from and a runbook note does not survive
    a copy-paste.
    """
    host = configured.strip()
    if "://" in host:
        host = host.split("://", 1)[1]
    return host.split("/", 1)[0].split(":", 1)[0]


def _required_env(name: str) -> str:
    """One credential, endpoint, or model id for the live wiring (CP-049):
    read here, once, and passed down as a constructor argument -- no
    adapter module reads the environment itself. A missing or blank value
    fails now, naming the variable, instead of surfacing as a 500 on
    whichever request first needed it."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"CLEARCUT_MODE=live requires the {name!r} environment variable, which is not set"
        )
    return value


def _build_live_use_cases(
    *,
    ch_client: _ChClient | None = None,
    vector_store: _VectorStore | None = None,
) -> _UseCaseGraph:
    """The live wiring seam CP-049 fills (Decision D38): the eight live
    adapters, built from environment-read credentials, with the two vendor
    clients that connect during construction --
    `clickhouse_connect.get_client` and `BigQueryVectorStore` -- accepted as
    plain keyword arguments whose default builds the real, connected thing.
    A unit test injects a fake for either and builds the rest of the graph
    for real, with no network; production omits both and gets eager,
    fail-loud construction, so a bad credential fails the Cloud Run revision
    rather than a request."""
    project = _required_env("GOOGLE_CLOUD_PROJECT")
    processor_id = _required_env("DOCAI_PROCESSOR_ID")
    gemini_model = _required_env("GEMINI_MODEL")
    gemini_model_lite = _required_env("GEMINI_MODEL_LITE")
    parallel_api_key = _required_env("PARALLEL_API_KEY")
    clickhouse_host = _clickhouse_host(_required_env("CLICKHOUSE_HOST"))
    clickhouse_user = _required_env("CLICKHOUSE_USER")
    clickhouse_password = _required_env("CLICKHOUSE_PASSWORD")
    data_store_id = _required_env("VERTEX_SEARCH_DATA_STORE_ID")
    webhook_url = _required_env("NOTIFY_WEBHOOK_URL")

    if ch_client is None:
        # cast: `Client.query` returns `Sequence[Sequence[Any]]` rows, one
        # step wider than `_ChClient`'s own `list[tuple[Any, ...]]` -- true
        # at runtime, invisible to mypy strict structurally.
        ch_client = cast(
            _ChClient,
            clickhouse_connect.get_client(
                host=clickhouse_host,
                username=clickhouse_user,
                password=clickhouse_password,
                secure=True,
            ),
        )

    embeddings = VertexAIEmbeddings(project=project, location=_GCP_LOCATION, model=_EMBEDDING_MODEL)
    if vector_store is None:
        vector_store = BigQueryVectorStore(
            embedding=embeddings,
            project_id=project,
            dataset_name=_BIGQUERY_DATASET,
            table_name=_BIGQUERY_LORE_TABLE,
            location=_GCP_LOCATION,
        )

    genai_client = genai.Client(vertexai=True, project=project, location=_GENAI_LOCATION)
    documentai_client = documentai.DocumentProcessorServiceClient()

    ingestion = DocumentAIIngestion(documentai_client, processor_id)
    extractor = GeminiSceneExtractor(genai_client, gemini_model)
    grounding = VertexSearchGrounding(genai_client.models, data_store_id)
    research = ParallelRightsResearch(httpx.Client(), parallel_api_key)
    continuity = GeminiContinuityCheck(genai_client, gemini_model_lite)
    lore = BigQueryLoreStore(vector_store, embeddings)
    tracker = ClickHouseTrackerStore(ch_client)
    notifier = WebhookNotifier(httpx.Client(), webhook_url)

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
    # Before the SPA blueprint, which answers every unmatched path: registered
    # after it, `/api/health` would resolve to the SPA's JSON 404 instead.
    app.register_blueprint(create_health_blueprint(mode))
    app.register_blueprint(
        create_spa_blueprint(build_dir if build_dir is not None else _default_build_dir())
    )
    return app
