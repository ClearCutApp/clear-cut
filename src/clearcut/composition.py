"""The single wiring point (AGENT.md Section 2 rule 4): `create_app()` is the
Cloud Run entry point `gcloud run deploy --source .` starts.

`CLEARCUT_MODE` selects the wiring (CHECKPOINTS.md Decision D36): `mock`
builds CP-043's in-memory demo adapters over the SDD Section 8(d) scenario and
reads no credential at all; `live` delegates to the adapter graph CP-049
fills, the seam Decision D38 chose (a plain constructor argument with a
real, eager-connecting default, not a lazy wrapper). An absent variable means
`live`, so a deployment that forgot to set it never serves planted data
instead of a loud startup failure. An unrecognized value is fatal at startup
too, naming the variable and both accepted values -- the fallback nobody
notices is the one that ships.

One `if`, one wiring function per branch, the same six route factories below
both -- plain constructor injection, no DI container, no service locator, no
module-level singleton, no registry (AGENT.md Section 4). Nothing is built at
import time: two `create_app()` calls each build a fresh `_UseCaseGraph`, so
they never share state.

`_register_api` is the one piece of structure this module grew when the HTTP
adapter was partitioned into six domains (ADR 0012). It is a mechanical
extraction inside this file, not a second wiring module: D79 keeps wiring in
one place, and six `register_blueprint` calls in the middle of `create_app`
buried the mode switch they sit under.

The analysis runner is the other addition (ADR 0013). The pipeline now runs on
a background thread, so the request that queued it returns before the work
starts and the route can no longer hold the root trace span open across it.
The span is opened inside the runner instead, and the runner is supplied here
because `application/` may not import opentelemetry.
"""

import json
import logging
import math
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar, cast

import clickhouse_connect
import firebase_admin
import httpx
from flask import Flask
from google import genai
from google.cloud import bigquery, firestore, storage
from google.cloud import documentai_v1 as documentai
from google.cloud.speech_v2 import SpeechClient
from langchain_google_vertexai import VertexAIEmbeddings
from opentelemetry import context as otel_context
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from clearcut.adapters.bigquery.lore_store import BigQueryLoreStore, _VectorStore
from clearcut.adapters.bigquery.scene_vectors import BigQuerySceneVectors
from clearcut.adapters.bigquery.vectors import BigQueryVectors
from clearcut.adapters.clickhouse.activity import ClickHouseActivity
from clearcut.adapters.clickhouse.analyses import ClickHouseAnalysisJobStore
from clearcut.adapters.clickhouse.client import _ChClient, bare_host
from clearcut.adapters.clickhouse.findings import ClickHouseFindingStore
from clearcut.adapters.clickhouse.projects import ClickHouseProjectStore
from clearcut.adapters.clickhouse.scripts import ClickHouseScriptStore
from clearcut.adapters.clickhouse.tracker import ClickHouseTrackerStore
from clearcut.adapters.demo.in_memory import (
    InMemoryAnalysisJobStore,
    InMemoryContinuityCheck,
    InMemoryFindingStore,
    InMemoryLegalGrounding,
    InMemoryLoreStore,
    InMemoryNotifier,
    InMemoryProjectStore,
    InMemoryRightsResearch,
    InMemorySceneExtractor,
    InMemoryScriptIngestion,
    InMemoryScriptStorage,
    InMemoryScriptStore,
    InMemoryTrackerStore,
)
from clearcut.adapters.gcp.document_ai import DocumentAIIngestion
from clearcut.adapters.gcp.firebase_identity import FirebaseIdentityVerifier
from clearcut.adapters.gcp.firestore_access import FirestoreProjectAccess
from clearcut.adapters.gcp.project_settings import FirestoreProjectSettings
from clearcut.adapters.gcp.speech import GoogleSpeechTranscription
from clearcut.adapters.gcp.storage import GcsScriptStorage, _StorageClient
from clearcut.adapters.gcp.teams import FirestoreTeams
from clearcut.adapters.gcp.vertex_search import VertexSearchGrounding
from clearcut.adapters.gemini.continuity import GeminiContinuityCheck
from clearcut.adapters.gemini.extractor import GeminiSceneExtractor
from clearcut.adapters.http.bible import create_bible_blueprint
from clearcut.adapters.http.identity import install_identity_boundary
from clearcut.adapters.http.openapi import build_spec
from clearcut.adapters.http.projects import create_projects_blueprint
from clearcut.adapters.http.questions import create_questions_blueprint
from clearcut.adapters.http.scripts import create_scripts_blueprint
from clearcut.adapters.http.spa import create_spa_blueprint
from clearcut.adapters.http.system import create_system_blueprint
from clearcut.adapters.http.tracker import create_tracker_blueprint
from clearcut.adapters.http.voice import create_voice_blueprint
from clearcut.adapters.http.workspaces import create_workspaces_blueprint
from clearcut.adapters.notify.webhook import WebhookNotifier
from clearcut.adapters.parallel.research import ParallelRightsResearch
from clearcut.application.activity_ports import ActivityStore
from clearcut.application.add_bible_facts import AddBibleFacts
from clearcut.application.analyze_script import AnalyzeScript
from clearcut.application.answer_project_question import AnswerProjectQuestion
from clearcut.application.create_project import CreateProject
from clearcut.application.evaluate_delta import EvaluateDelta
from clearcut.application.get_analysis import GetAnalysis
from clearcut.application.get_bible import GetBible
from clearcut.application.get_project import GetProject
from clearcut.application.get_script import GetScript
from clearcut.application.get_tracker_item import GetTrackerItem
from clearcut.application.list_projects import ListProjects
from clearcut.application.list_scripts import ListScripts
from clearcut.application.list_tracker_items import ListTrackerItems
from clearcut.application.resolve_finding import ResolveFinding
from clearcut.application.start_analysis import Runner, StartAnalysis, Work
from clearcut.application.upload_script_file import UploadScriptFile
from clearcut.application.workspace_ports import OwnedFiles, ProjectAccess
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.finding import Finding
from clearcut.observability import stage_span
from clearcut.provider_config import ProviderConfig

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

_ANALYSIS_SPAN = "analyze"

# What `bind_context` hands back, unchanged: it wraps a callable, it does not
# decide what that callable returns.
_R = TypeVar("_R")


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


def record_findings_total(findings: tuple[Finding, ...]) -> None:
    """Emits `clearcut_findings_total`, one point per finding, labelled by risk
    level and category (ADR 0008, SDD Section 6).

    This used to run in the analyze route, straight after the use case
    returned. Since ADR 0013 that route answers 202 before a single finding
    exists, so the count is taken where the run actually ends and reaches this
    layer as the callable `StartAnalysis` was given.

    The meter is resolved per call for the same reason the tracer is: a
    module-level lookup caches a proxy from before `_configure_telemetry`
    installed the real provider.
    """
    counter = metrics.get_meter(__name__).create_counter(
        "clearcut_findings_total", description="Findings emitted, by risk level and category"
    )
    for finding in findings:
        counter.add(1, {"risk_level": finding.risk_level.value, "category": finding.category.value})


def run_traced(script_id: str, work: Work) -> None:
    """Runs one analysis under a root span carrying its `script_id`.

    The five stage spans the adapters open nest under this one and share its
    trace id, which is what makes a run readable in Grafana as a single
    trace. `trace.get_tracer(__name__)` is looked up on every call rather
    than cached at import time -- a module-level `ProxyTracer` resolved
    before `_configure_telemetry` installs the real provider caches that
    first resolution permanently.
    """
    with stage_span(trace.get_tracer(__name__), _ANALYSIS_SPAN) as span:
        span.set_attribute("script_id", script_id)
        work()


def bind_context(work: Callable[[], _R]) -> Callable[[], _R]:
    """Carries this thread's OpenTelemetry context onto whichever thread runs
    `work`, so a span opened inside it nests under the caller's span instead
    of starting a trace of its own.

    Here rather than in `application/concurrency.py` for the same reason
    `run_traced` is here rather than in a use case: `application/` may not
    import opentelemetry (AGENT.md Section 2 rule 2). Without this, the
    per-finding `ground` and `research` spans the adapters open on a pool
    thread each become a root span with a fresh trace id, and one analysis
    arrives in Grafana as a handful of unrelated traces.

    `attach` returns a token that `detach` needs back, and the pool reuses its
    threads across items, so the `try/finally` is not decoration: a leaked
    attach would leave the next item running under a finished span's context.
    """
    context = otel_context.get_current()

    def bound() -> _R:
        token = otel_context.attach(context)
        try:
            return work()
        finally:
            otel_context.detach(token)

    return bound


def run_traced_in_background(script_id: str, work: Work) -> None:
    """`run_traced` on a daemon thread, so the request that queued the run
    returns while it is still going (ADR 0013).

    Daemon rather than joined: the job row in ClickHouse is the source of
    truth, and a process shutting down mid-run leaves a row the next read
    reaps as stale. A non-daemon thread would instead hold the container
    open for the twenty minutes the run takes.
    """
    threading.Thread(target=lambda: run_traced(script_id, work), daemon=True).start()


@dataclass(frozen=True)
class _UseCaseGraph:
    """Every use case the six route factories mount -- one graph per mode
    branch, same shape, so a route cannot depend on which branch built it."""

    analyze_script: AnalyzeScript
    evaluate_delta: EvaluateDelta
    start_analysis: StartAnalysis
    get_analysis: GetAnalysis
    create_project: CreateProject
    list_projects: ListProjects
    get_project: GetProject
    upload_script_file: UploadScriptFile
    list_scripts: ListScripts
    get_script: GetScript
    list_tracker_items: ListTrackerItems
    get_tracker_item: GetTrackerItem
    resolve_finding: ResolveFinding
    get_bible: GetBible
    add_bible_facts: AddBibleFacts
    answer_project_question: AnswerProjectQuestion
    provider_config_json: str = "{}"
    activity: ActivityStore | None = None


def _build_mock_use_cases(runner: Runner) -> _UseCaseGraph:
    """Wires CP-043's demo adapters into every use case: no credential read,
    no vendor client built, no socket opened. Each store is shared across the
    use cases that need it, so a write from one route (a queued analysis) is
    visible to another (a tracker or script read)."""
    ingestion = InMemoryScriptIngestion()
    extractor = InMemorySceneExtractor()
    grounding = InMemoryLegalGrounding()
    research = InMemoryRightsResearch()
    continuity = InMemoryContinuityCheck()
    lore = InMemoryLoreStore()
    scripts = InMemoryScriptStore()
    tracker = InMemoryTrackerStore(scripts)
    notifier = InMemoryNotifier()
    projects = InMemoryProjectStore()
    findings = InMemoryFindingStore()
    jobs = InMemoryAnalysisJobStore()
    script_storage = InMemoryScriptStorage()
    analyze_script = AnalyzeScript(
        ingestion,
        extractor,
        grounding,
        research,
        lore,
        tracker,
        continuity,
        findings,
        bind=bind_context,
    )
    evaluate_delta = EvaluateDelta(
        ingestion,
        extractor,
        grounding,
        research,
        lore,
        tracker,
        continuity,
        notifier,
        findings,
        bind=bind_context,
    )
    return _UseCaseGraph(
        analyze_script=analyze_script,
        evaluate_delta=evaluate_delta,
        start_analysis=StartAnalysis(
            jobs,
            analyze_script,
            evaluate_delta,
            runner=runner,
            on_findings=record_findings_total,
        ),
        get_analysis=GetAnalysis(jobs),
        create_project=CreateProject(projects),
        list_projects=ListProjects(projects),
        get_project=GetProject(projects),
        upload_script_file=UploadScriptFile(script_storage),
        list_scripts=ListScripts(scripts, findings),
        get_script=GetScript(scripts, findings),
        list_tracker_items=ListTrackerItems(tracker),
        get_tracker_item=GetTrackerItem(tracker),
        resolve_finding=ResolveFinding(tracker, notifier),
        get_bible=GetBible(lore),
        add_bible_facts=AddBibleFacts(lore),
        answer_project_question=AnswerProjectQuestion(lore, grounding, tracker),
    )


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


def _scene_vectors(project: str) -> BigQuerySceneVectors:
    def options(raw: str) -> ProviderConfig:
        return ProviderConfig.read({}, "unused", "unused", json.loads(raw))

    def store(raw: str) -> _VectorStore:
        providers = options(raw)
        return BigQueryVectors(
            bigquery.Client(project=project, location=_GCP_LOCATION),
            f"{project}.{_BIGQUERY_DATASET}.analysis_scene_vectors",
            location=_GCP_LOCATION,
            timeout=providers.bigquery_timeout,
            extra_columns=("organization_id", "analysis_id", "revision_id", "scene_id"),
        )

    def embed(texts: list[str], raw: str, query: bool) -> list[list[float]]:
        providers = options(raw)
        try:
            with genai.Client(
                vertexai=True,
                project=project,
                location=_GCP_LOCATION,
                http_options=genai.types.HttpOptions(
                    timeout=int(providers.genai_timeout * 1000),
                    retry_options=genai.types.HttpRetryOptions(attempts=1),
                ),
            ) as client:
                response = client.models.embed_content(
                    model=providers.embedding_model,
                    contents=cast(list[genai.types.ContentUnionDict], texts),
                    config=genai.types.EmbedContentConfig(
                        task_type="RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT",
                        auto_truncate=False,
                    ),
                )
            embeddings = [list(item.values or []) for item in response.embeddings or []]
            if len(embeddings) != len(texts) or any(
                not vector or not all(math.isfinite(v) for v in vector) for vector in embeddings
            ):
                raise ValueError("invalid embedding result")
            return embeddings
        except Exception as exc:
            raise SourceUnavailable("scene embeddings unavailable") from exc

    return BigQuerySceneVectors(store, embed)


def _build_live_use_cases(
    *,
    runner: Runner = run_traced_in_background,
    ch_client: _ChClient | None = None,
    vector_store: _VectorStore | None = None,
    storage_client: _StorageClient | None = None,
    provider_config: dict[str, str] | None = None,
) -> _UseCaseGraph:
    """The live wiring seam CP-049 fills (Decision D38): the live adapters,
    built from environment-read credentials, with the vendor clients that
    connect or resolve credentials during construction accepted as plain
    keyword arguments whose default builds the real, connected thing. A unit
    test injects a fake for any of them and builds the rest of the graph for
    real, with no network; production omits them and gets eager, fail-loud
    construction, so a bad credential fails the Cloud Run revision rather
    than a request.

    The four ClickHouse stores share one client. They are separate ports
    because a route that reads scripts has no business holding the tracker's
    writes (AGENT.md Section 3, ISP), but they are one connection, and
    `script_versions` is one table `ClickHouseScriptStore` and
    `ClickHouseTrackerStore` both address."""
    project = _required_env("GOOGLE_CLOUD_PROJECT")
    processor_id = _required_env("DOCAI_PROCESSOR_ID")
    gemini_model = _required_env("GEMINI_MODEL")
    gemini_model_lite = _required_env("GEMINI_MODEL_LITE")
    providers = ProviderConfig.read(os.environ, gemini_model, gemini_model_lite, provider_config)
    selected = providers.frozen()
    gemini_model, gemini_model_lite = providers.gemini_model, providers.gemini_model_lite
    parallel_api_key = _required_env("PARALLEL_API_KEY")
    clickhouse_host = bare_host(_required_env("CLICKHOUSE_HOST"))
    clickhouse_user = _required_env("CLICKHOUSE_USER")
    clickhouse_password = _required_env("CLICKHOUSE_PASSWORD")
    data_store_id = _required_env("VERTEX_SEARCH_DATA_STORE_ID")
    webhook_url = _required_env("NOTIFY_WEBHOOK_URL")
    intake_bucket = _required_env("SCRIPTS_INTAKE_BUCKET")

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
                connect_timeout=providers.clickhouse_connect_timeout,
                send_receive_timeout=providers.clickhouse_request_timeout,
                query_retries=0,
            ),
        )

    genai_client = genai.Client(
        vertexai=True,
        project=project,
        location=_GENAI_LOCATION,
        http_options=genai.types.HttpOptions(
            timeout=int(providers.genai_timeout * 1000),
            retry_options=genai.types.HttpRetryOptions(attempts=1),
        ),
    )
    embedding_client = genai.Client(
        vertexai=True,
        project=project,
        location=_GCP_LOCATION,
        http_options=genai.types.HttpOptions(
            timeout=int(providers.genai_timeout * 1000),
            retry_options=genai.types.HttpRetryOptions(attempts=1),
        ),
    )
    embeddings = VertexAIEmbeddings(
        project=project,
        location=_GCP_LOCATION,
        model=providers.embedding_model,
        client=embedding_client,
        max_retries=1,
    )
    # SDK 3.2.4's validator replaces the constructor's public client field.
    # Assign it after validation so embeddings retain their regional budget.
    embeddings.client.close()
    embeddings.client = embedding_client
    if vector_store is None:
        vector_store = BigQueryVectors(
            bigquery.Client(project=project, location=_GCP_LOCATION),
            f"{project}.{_BIGQUERY_DATASET}.{_BIGQUERY_LORE_TABLE}",
            location=_GCP_LOCATION,
        )
    if storage_client is None:
        storage_client = storage.Client(project=project)

    documentai_client = documentai.DocumentProcessorServiceClient()

    ingestion = DocumentAIIngestion(
        documentai_client, processor_id, timeout=providers.document_timeout
    )
    extractor = GeminiSceneExtractor(genai_client, gemini_model)
    grounding = VertexSearchGrounding(genai_client.models, data_store_id)
    research = ParallelRightsResearch(httpx.Client(), parallel_api_key)
    continuity = GeminiContinuityCheck(genai_client, gemini_model_lite)
    lore = BigQueryLoreStore(vector_store, embeddings)
    tracker = ClickHouseTrackerStore(ch_client)
    notifier = WebhookNotifier(httpx.Client(), webhook_url)
    projects = ClickHouseProjectStore(ch_client)
    scripts = ClickHouseScriptStore(ch_client)
    findings = ClickHouseFindingStore(ch_client)
    jobs = ClickHouseAnalysisJobStore(ch_client)
    script_storage = GcsScriptStorage(storage_client, intake_bucket)

    analyze_script = AnalyzeScript(
        ingestion,
        extractor,
        grounding,
        research,
        lore,
        tracker,
        continuity,
        findings,
        bind=bind_context,
    )
    evaluate_delta = EvaluateDelta(
        ingestion,
        extractor,
        grounding,
        research,
        lore,
        tracker,
        continuity,
        notifier,
        findings,
        bind=bind_context,
    )
    return _UseCaseGraph(
        provider_config_json=json.dumps(selected, sort_keys=True),
        activity=ClickHouseActivity(ch_client),
        analyze_script=analyze_script,
        evaluate_delta=evaluate_delta,
        start_analysis=StartAnalysis(
            jobs,
            analyze_script,
            evaluate_delta,
            runner=runner,
            on_findings=record_findings_total,
        ),
        get_analysis=GetAnalysis(jobs),
        create_project=CreateProject(projects),
        list_projects=ListProjects(projects),
        get_project=GetProject(projects),
        upload_script_file=UploadScriptFile(script_storage),
        list_scripts=ListScripts(scripts, findings),
        get_script=GetScript(scripts, findings),
        list_tracker_items=ListTrackerItems(tracker),
        get_tracker_item=GetTrackerItem(tracker),
        resolve_finding=ResolveFinding(tracker, notifier),
        get_bible=GetBible(lore),
        add_bible_facts=AddBibleFacts(lore),
        answer_project_question=AnswerProjectQuestion(lore, grounding, tracker),
    )


def _default_build_dir() -> Path:
    """`web/dist`, the Vite build output ADR 0010 says this container serves
    -- computed here, inside the function, on every call, rather than as a
    module-level constant: importing this module must never touch the
    filesystem, and a test must be free to point `create_app` at any
    directory it likes instead.

    The working directory comes first because that is where the container has
    it: the Dockerfile copies the Vite output to `/app/web/dist` and `pip
    install` puts the package under site-packages, so walking up from
    `__file__` lands on `/usr/local/lib/python3.12` instead. The deployed
    revision served `SPA build not found at /usr/local/lib/python3.12/web/dist`
    until this looked at the process first (CP-060). Local runs never showed it,
    because `pip install -e` leaves the package inside the repo and both paths
    agree.

    The package-relative path stays as the fallback so the error message names
    somewhere a developer recognises rather than whatever directory the process
    happened to start in."""
    from_cwd = Path.cwd() / "web" / "dist"
    if from_cwd.is_dir():
        return from_cwd
    return Path(__file__).resolve().parent.parent.parent / "web" / "dist"


def _register_api(
    app: Flask,
    graph: _UseCaseGraph,
    mode: str,
    build_dir: Path,
    access: ProjectAccess | None = None,
    owned_files: OwnedFiles | None = None,
    client_config: dict[str, str] | None = None,
) -> None:
    """Mounts the six domain blueprints, then the SPA.

    Order is load-bearing and is the reason this is one function rather than
    six calls scattered through `create_app`: the SPA blueprint answers every
    unmatched path, so a domain registered after it would resolve to the
    SPA's JSON 404 for `/api` paths. It goes last, once.
    """
    app.register_blueprint(create_system_blueprint(mode, build_spec, client_config))
    app.register_blueprint(
        create_projects_blueprint(
            graph.create_project, graph.list_projects, graph.get_project, access
        )
    )
    app.register_blueprint(
        create_scripts_blueprint(
            graph.upload_script_file,
            graph.list_scripts,
            graph.get_script,
            graph.start_analysis,
            graph.get_analysis,
        )
    )
    app.register_blueprint(
        create_tracker_blueprint(
            graph.list_tracker_items, graph.get_tracker_item, graph.resolve_finding
        )
    )
    app.register_blueprint(create_bible_blueprint(graph.get_bible, graph.add_bible_facts))
    app.register_blueprint(create_questions_blueprint(graph.answer_project_question))
    app.register_blueprint(create_spa_blueprint(build_dir))


def create_app(build_dir: Path | None = None, *, analysis_runner: Runner | None = None) -> Flask:
    """The Cloud Run entry point. Builds a fresh `_UseCaseGraph` per call and
    mounts it through the six domain blueprints, alongside CP-046's SPA
    blueprint serving `build_dir` (default `web/dist`) -- one origin for the
    JSON API and the static build (ADR 0010), so no CORS configuration is
    ever needed.

    `analysis_runner` is the same kind of seam D38 chose for the vendor
    clients: production omits it and gets the background thread ADR 0013
    specifies, and a test passes `run_traced` to run the pipeline inside the
    request instead, so it can assert on what the run produced without
    polling a thread."""
    _configure_telemetry()
    runner = analysis_runner if analysis_runner is not None else run_traced_in_background
    mode = os.environ.get(_MODE_ENV_VAR, _LIVE_MODE)
    if mode == _MOCK_MODE:
        logger.warning(
            "CLEARCUT_MODE=mock: serving the planted demo scenario, no live service is connected"
        )
        use_cases = _build_mock_use_cases(runner)
    elif mode == _LIVE_MODE:
        use_cases = _build_live_use_cases(runner=runner)
    else:
        raise ValueError(
            f"{_MODE_ENV_VAR}={mode!r} is not recognized; set it to "
            f"{_MOCK_MODE!r} or {_LIVE_MODE!r}"
        )

    app = Flask(__name__)
    access: FirestoreProjectAccess | None = None
    if mode == _LIVE_MODE:
        firebase_app = firebase_admin.initialize_app(
            options={"projectId": _required_env("GOOGLE_CLOUD_PROJECT")},
            name=f"clearcut-{id(app)}",
        )
        access = FirestoreProjectAccess(
            firestore.Client(project=_required_env("GOOGLE_CLOUD_PROJECT"))
        )
        install_identity_boundary(app, FirebaseIdentityVerifier(firebase_app), access)
    voice_options = json.loads(use_cases.provider_config_json)
    speech = (
        GoogleSpeechTranscription(
            SpeechClient(client_options={"api_endpoint": "us-central1-speech.googleapis.com"}),
            _required_env("GOOGLE_CLOUD_PROJECT"),
            model=voice_options.get("speech_model", "chirp_2"),
            timeout=float(voice_options.get("speech_timeout", 45)),
        )
        if mode == _LIVE_MODE
        else None
    )
    app.register_blueprint(create_voice_blueprint(speech))
    app.register_blueprint(
        create_workspaces_blueprint(
            FirestoreTeams(firestore.Client(project=_required_env("GOOGLE_CLOUD_PROJECT")))
            if access is not None
            else None,
            FirestoreProjectSettings(
                firestore.Client(project=_required_env("GOOGLE_CLOUD_PROJECT"))
            )
            if access is not None
            else None,
        )
    )
    _register_api(
        app,
        use_cases,
        mode,
        build_dir if build_dir is not None else _default_build_dir(),
        access,
        access,
        {
            "apiKey": os.environ.get("FIREBASE_WEB_API_KEY", ""),
            "authDomain": os.environ.get("FIREBASE_WEB_AUTH_DOMAIN", ""),
            "projectId": os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
            "appId": os.environ.get("FIREBASE_WEB_APP_ID", ""),
        },
    )
    return app
