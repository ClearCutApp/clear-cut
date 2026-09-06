"""Unit tests for `composition.py`'s app factory and mode switch (CP-048,
D36, D38).

The headline test (`test_mock_mode_...`) clears the environment down to
`CLEARCUT_MODE=mock` and drives `POST /api/analyze` then `GET /api/tracker`
through a real Flask test client -- the whole of D36 in one test, per
CHECKPOINTS.md's own framing: the MVP runs today, on nothing.

The live-branch tests below (CP-049) fake only the two vendor clients that
connect during construction -- `_ChClient` and `_VectorStore` (D38) -- and let
the rest of the live graph build for real. Every other vendor constructor in
that graph is provably non-connecting at construction time (verified by hand
against this repo's own `.venv` before writing these tests):
`google.genai.Client`, `VertexAIEmbeddings` (which builds a `genai.Client`
internally), `parallel.Parallel`, and `httpx.Client` all defer authentication
and I/O to the first real call. The one exception is
`documentai.DocumentProcessorServiceClient`, whose GAPIC-generated
constructor resolves `google.auth.default()` eagerly -- with no local
credential, that falls through to a GCE metadata-server probe that hangs for
several seconds in a sandbox with no route to it. `_write_fake_adc` points
`GOOGLE_APPLICATION_CREDENTIALS` at a syntactically valid but entirely
fabricated `authorized_user` ADC file so that resolves locally instead,
keeping the suite fast and deterministic without touching `composition.py`'s
own shape.
"""

import json
import logging
import os
import socket
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest
from flask import Flask

from clearcut import composition
from clearcut.adapters.bigquery.lore_store import BigQueryLoreStore
from clearcut.adapters.clickhouse.tracker import ClickHouseTrackerStore
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
from clearcut.adapters.notify.webhook import WebhookNotifier
from clearcut.adapters.parallel.research import ParallelRightsResearch
from clearcut.application.start_analysis import Work
from clearcut.composition import (
    _GCP_LOCATION,
    _GENAI_LOCATION,
    _build_live_use_cases,
    _build_mock_use_cases,
    _clickhouse_host,
    _default_build_dir,
    create_app,
    run_traced,
)

_ANALYZE_BODY = {
    "project_id": "demo-project",
    "jurisdiction_code": "AR",
    "gcs_uri": "gs://clearcut-demo/planted-script-v1.pdf",
    "version": 1,
}


def _clear_env(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    """Replaces `os.environ` outright, so a test proves mock mode reads
    nothing beyond `CLEARCUT_MODE` rather than merely not reading twelve
    named variables that happen to be unset in this shell."""
    monkeypatch.setattr(os, "environ", dict(overrides))


# ---------------------------------------------------------------------------
# Criterion 1: create_app() mounts CP-029's blueprint through its frozen
# five-argument factory.
# ---------------------------------------------------------------------------


def test_create_app_returns_a_flask_app_with_the_demo_routes_mounted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch, CLEARCUT_MODE="mock")
    app = create_app()
    assert isinstance(app, Flask)
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/projects/<project_id>/scripts" in rules
    assert "/api/projects/<project_id>/tracker-items" in rules


# ---------------------------------------------------------------------------
# Criterion 2: CLEARCUT_MODE selects the wiring; mock builds the demo
# adapters, by type.
# ---------------------------------------------------------------------------


def run_inline(_script_id: str, work: Work) -> None:
    """Runs the queued work on the calling thread.

    `run_traced_in_background` hands the run to a daemon thread, which is
    right in production and useless in a build-only test: the assertions
    below would race the run rather than observe it. Every test that wants
    the pipeline to have finished by the time it looks passes this instead
    (ADR 0013 puts the seam here for exactly that reason).
    """
    work()


def test_build_mock_use_cases_wires_the_demo_adapters_by_type() -> None:
    graph = _build_mock_use_cases(run_inline)
    assert isinstance(graph.analyze_script._ingestion, InMemoryScriptIngestion)
    assert isinstance(graph.analyze_script._extractor, InMemorySceneExtractor)
    assert isinstance(graph.analyze_script._grounding, InMemoryLegalGrounding)
    assert isinstance(graph.analyze_script._research, InMemoryRightsResearch)
    assert isinstance(graph.analyze_script._lore, InMemoryLoreStore)
    assert isinstance(graph.analyze_script._tracker, InMemoryTrackerStore)
    assert isinstance(graph.analyze_script._continuity, InMemoryContinuityCheck)
    assert isinstance(graph.evaluate_delta._notifier, InMemoryNotifier)
    assert isinstance(graph.list_tracker_items._tracker, InMemoryTrackerStore)
    assert isinstance(graph.resolve_finding._notifier, InMemoryNotifier)
    assert isinstance(graph.answer_project_question._lore, InMemoryLoreStore)


def test_build_mock_use_cases_shares_one_tracker_store_across_use_cases() -> None:
    """`POST /api/analyze` writes through `AnalyzeScript`; `GET /api/tracker`
    reads through `ListTrackerItems`. Two separate `InMemoryTrackerStore`
    instances would make the second call blind to the first call's write."""
    graph = _build_mock_use_cases(run_inline)
    assert graph.analyze_script._tracker is graph.list_tracker_items._tracker
    assert graph.analyze_script._tracker is graph.resolve_finding._tracker


# ---------------------------------------------------------------------------
# Criterion 3: mock mode needs no credentials, opens no socket, and drives
# the SDD Section 8(d) scenario end to end over a fully cleared environment.
# ---------------------------------------------------------------------------


def test_mock_mode_needs_no_credentials_and_drives_the_sdd_8d_scenario(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch, CLEARCUT_MODE="mock")
    client = create_app(analysis_runner=run_traced).test_client()

    queued = client.post("/api/projects/demo-project/scripts", json=_ANALYZE_BODY)
    assert queued.status_code == 202
    location = queued.headers["Location"]

    analysis = client.get(location)
    assert analysis.status_code == 200
    assert analysis.get_json()["state"] == "SUCCEEDED"

    # The reload is the point of ADR 0014. Before findings were persisted this
    # read returned nothing, because a finding existed only in the body of the
    # response that produced it -- so Script Review was empty the moment a
    # producer refreshed the page.
    script_id = queued.get_json()["script_id"]
    script = client.get(f"/api/projects/demo-project/scripts/{script_id}")
    assert script.status_code == 200
    body = script.get_json()

    findings_by_category = {finding["category"]: finding for finding in body["findings"]}
    assert len(body["findings"]) == 3
    assert findings_by_category["INDUSTRIAL_PROPERTY"]["page"] == 3
    assert findings_by_category["COPYRIGHT_WORKS"]["page"] == 5
    assert findings_by_category["CONTINUITY"]["page"] == 8

    tracker_response = client.get("/api/projects/demo-project/tracker-items")
    assert tracker_response.status_code == 200
    items = tracker_response.get_json()
    assert len(items) == 3
    assert all(item["state"] == "BLOCKED" for item in items)


# ---------------------------------------------------------------------------
# Criterion 4: an unrecognized CLEARCUT_MODE fails at startup naming the
# variable and both accepted values.
# ---------------------------------------------------------------------------


def test_unrecognized_mode_fails_at_startup_naming_the_variable_and_both_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch, CLEARCUT_MODE="demo")
    with pytest.raises(ValueError, match="CLEARCUT_MODE"):
        create_app()
    _clear_env(monkeypatch, CLEARCUT_MODE="demo")
    with pytest.raises(ValueError, match="mock"):
        create_app()
    _clear_env(monkeypatch, CLEARCUT_MODE="demo")
    with pytest.raises(ValueError, match="live"):
        create_app()


# ---------------------------------------------------------------------------
# Criterion 5: live mode fails at startup naming the live wiring as
# incomplete, and never falls back to mock.
# ---------------------------------------------------------------------------


def test_live_mode_fails_at_startup_naming_the_live_wiring_as_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch, CLEARCUT_MODE="live")
    with pytest.raises(RuntimeError, match="live"):
        create_app()


def test_live_wiring_itself_raises_rather_than_returning_a_mock_wired_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proves the failure originates inside the live branch's own wiring
    function, not somewhere in `create_app()` that could be bypassed --
    so the live branch never quietly returns the mock-wired graph. Clears
    the environment first (CP-049): `_build_live_use_cases` now reads ten
    credentials of its own, so this must not depend on whatever the ambient
    shell running the suite happens to have set."""
    _clear_env(monkeypatch, CLEARCUT_MODE="live")
    with pytest.raises(RuntimeError):
        _build_live_use_cases()


def test_absent_mode_defaults_to_live_and_fails_the_same_way(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch)
    with pytest.raises(RuntimeError, match="live"):
        create_app()


# ---------------------------------------------------------------------------
# Criterion 6: mock mode announces itself once at startup with a WARNING.
# ---------------------------------------------------------------------------


def test_mock_mode_logs_exactly_one_startup_warning_naming_the_mode(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _clear_env(monkeypatch, CLEARCUT_MODE="mock")
    with caplog.at_level(logging.WARNING):
        create_app()
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "mock" in warnings[0].message


# ---------------------------------------------------------------------------
# Criterion 7: plain constructor injection; two create_app() calls produce
# independent instances.
# ---------------------------------------------------------------------------


def test_two_create_app_calls_produce_independent_instances(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch, CLEARCUT_MODE="mock")
    first_client = create_app().test_client()
    _clear_env(monkeypatch, CLEARCUT_MODE="mock")
    second_client = create_app().test_client()

    first_client.post("/api/projects/demo-project/scripts", json=_ANALYZE_BODY)
    second_tracker = second_client.get("/api/projects/demo-project/tracker-items")

    assert second_tracker.get_json() == []


# ---------------------------------------------------------------------------
# CP-049: the live branch. Fakes stand in only for `_ChClient` and
# `_VectorStore` -- the two vendor clients that connect during construction
# (D38) -- so a unit test can build the whole live graph without a socket.
# ---------------------------------------------------------------------------

_LIVE_ENV_VALUES = {
    "GOOGLE_CLOUD_PROJECT": "clearcut-dummy-project",
    "DOCAI_PROCESSOR_ID": "projects/clearcut-dummy-project/locations/us/processors/dummy",
    "GEMINI_MODEL": "gemini-3.7-flash",
    "GEMINI_MODEL_LITE": "gemini-3.1-flash-lite",
    "PARALLEL_API_KEY": "dummy-parallel-key",
    "CLICKHOUSE_HOST": "clickhouse-unreachable.invalid",
    "CLICKHOUSE_USER": "dummy-ch-user",
    "CLICKHOUSE_PASSWORD": "dummy-ch-password",
    "VERTEX_SEARCH_DATA_STORE_ID": "dummy-data-store",
    "NOTIFY_WEBHOOK_URL": "https://notify.example.invalid/webhook",
    "SCRIPTS_INTAKE_BUCKET": "clearcut-dummy-intake",
}


class _FakeChClient:
    """Satisfies `clickhouse/tracker.py`'s `_ChClient` protocol structurally
    (AGENT.md Section 5). Every method raises: this fake exists only to let
    the live graph build without a real ClickHouse connection, never to be
    called -- `_build_live_use_cases` wires it straight into
    `ClickHouseTrackerStore` and stops."""

    def command(self, cmd: str) -> NoReturn:
        raise AssertionError("_ChClient.command was called in a build-only test")

    def insert(self, table: str, data: list[list[Any]], column_names: list[str]) -> NoReturn:
        raise AssertionError("_ChClient.insert was called in a build-only test")

    def query(self, query: str, parameters: dict[str, Any] | None = None) -> NoReturn:
        raise AssertionError("_ChClient.query was called in a build-only test")


class _FakeVectorStore:
    """Satisfies `bigquery/lore_store.py`'s `_VectorStore` protocol
    structurally, for the same reason as `_FakeChClient` above."""

    def add_texts_with_embeddings(
        self,
        texts: list[str],
        embs: list[list[float]],
        metadatas: list[dict[str, str | int]] | None = None,
    ) -> NoReturn:
        raise AssertionError(
            "_VectorStore.add_texts_with_embeddings was called in a build-only test"
        )

    def similarity_search_by_vector_with_score(
        self,
        embedding: list[float],
        filter: dict[str, str] | None = None,
        k: int = 5,
    ) -> NoReturn:
        raise AssertionError(
            "_VectorStore.similarity_search_by_vector_with_score was called in a build-only test"
        )

    def get_documents(
        self, ids: list[str] | None = None, filter: dict[str, Any] | None = None
    ) -> NoReturn:
        raise AssertionError("_VectorStore.get_documents was called in a build-only test")


def _write_fake_adc(tmp_path: Path) -> str:
    """A syntactically valid but entirely fabricated `authorized_user` ADC
    file (google-auth's own on-disk format) -- not a real credential, and
    incapable of authenticating anything. See this module's docstring for
    why `documentai.DocumentProcessorServiceClient()` needs one even in a
    build-only test."""
    path = tmp_path / "fake_adc.json"
    path.write_text(
        json.dumps(
            {
                "client_id": "fake-client-id.apps.googleusercontent.com",
                "client_secret": "fake-client-secret",
                "refresh_token": "fake-refresh-token",
                "type": "authorized_user",
            }
        )
    )
    return str(path)


def _forbid_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fails the test the instant anything under it opens a real socket --
    the criterion 3 no-socket guarantee, proved rather than assumed."""

    def _refuse(self: socket.socket, address: object) -> NoReturn:
        raise AssertionError(f"a live adapter tried to open a socket to {address!r}")

    monkeypatch.setattr(socket.socket, "connect", _refuse)


# ---------------------------------------------------------------------------
# Criterion 1 and 3: the live branch builds the eight concrete adapters,
# wires them into the five use cases, and -- with fakes for the two
# connecting vendor clients -- does it without opening a socket.
# ---------------------------------------------------------------------------


def test_build_live_use_cases_wires_the_eight_live_adapters_with_no_socket(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_env(
        monkeypatch,
        CLEARCUT_MODE="live",
        GOOGLE_APPLICATION_CREDENTIALS=_write_fake_adc(tmp_path),
        **_LIVE_ENV_VALUES,
    )
    _forbid_sockets(monkeypatch)

    graph = _build_live_use_cases(ch_client=_FakeChClient(), vector_store=_FakeVectorStore())

    assert isinstance(graph.analyze_script._ingestion, DocumentAIIngestion)
    assert isinstance(graph.analyze_script._extractor, GeminiSceneExtractor)
    assert isinstance(graph.analyze_script._grounding, VertexSearchGrounding)
    assert isinstance(graph.analyze_script._research, ParallelRightsResearch)
    assert isinstance(graph.analyze_script._continuity, GeminiContinuityCheck)
    assert isinstance(graph.analyze_script._lore, BigQueryLoreStore)
    assert isinstance(graph.analyze_script._tracker, ClickHouseTrackerStore)
    assert isinstance(graph.evaluate_delta._notifier, WebhookNotifier)


def test_build_live_use_cases_wires_answer_project_question_to_the_live_collaborators(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The mock counterpart (`test_build_mock_use_cases_wires_the_demo_adapters_by_type`)
    asserts `answer_project_question`'s collaborator by type; this is the
    live-branch equivalent, closing the gap a demo store swapped into a live
    route would otherwise leave open (D36's exact named failure)."""
    _clear_env(
        monkeypatch,
        CLEARCUT_MODE="live",
        GOOGLE_APPLICATION_CREDENTIALS=_write_fake_adc(tmp_path),
        **_LIVE_ENV_VALUES,
    )
    _forbid_sockets(monkeypatch)

    graph = _build_live_use_cases(ch_client=_FakeChClient(), vector_store=_FakeVectorStore())

    assert isinstance(graph.answer_project_question._lore, BigQueryLoreStore)
    assert isinstance(graph.answer_project_question._grounding, VertexSearchGrounding)
    assert isinstance(graph.answer_project_question._tracker, ClickHouseTrackerStore)


def test_build_live_use_cases_passes_each_env_read_value_to_its_adapter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Criterion 2's second clause: every credential, endpoint, and model id
    must reach its adapter, not merely be read here. Proven by comparing each
    live adapter's stored attribute against its `_LIVE_ENV_VALUES` entry --
    including the two same-shape Gemini model ids, so a silent swap between
    `GEMINI_MODEL` and `GEMINI_MODEL_LITE` fails here rather than nowhere."""
    _clear_env(
        monkeypatch,
        CLEARCUT_MODE="live",
        GOOGLE_APPLICATION_CREDENTIALS=_write_fake_adc(tmp_path),
        **_LIVE_ENV_VALUES,
    )
    _forbid_sockets(monkeypatch)

    graph = _build_live_use_cases(ch_client=_FakeChClient(), vector_store=_FakeVectorStore())

    # Each collaborator is typed by its port (`Notifier`, `LegalGrounding`, ...)
    # on the use case that holds it, so mypy strict needs the `isinstance`
    # narrowing below before it accepts the adapter-specific attribute reads
    # that follow -- the same narrowing the sibling test above already does.
    notifier = graph.evaluate_delta._notifier
    grounding = graph.analyze_script._grounding
    ingestion = graph.analyze_script._ingestion
    extractor = graph.analyze_script._extractor
    continuity = graph.analyze_script._continuity
    assert isinstance(notifier, WebhookNotifier)
    assert isinstance(grounding, VertexSearchGrounding)
    assert isinstance(ingestion, DocumentAIIngestion)
    assert isinstance(extractor, GeminiSceneExtractor)
    assert isinstance(continuity, GeminiContinuityCheck)

    assert notifier._url == _LIVE_ENV_VALUES["NOTIFY_WEBHOOK_URL"]
    assert grounding._data_store_id == _LIVE_ENV_VALUES["VERTEX_SEARCH_DATA_STORE_ID"]
    assert ingestion._processor_id == _LIVE_ENV_VALUES["DOCAI_PROCESSOR_ID"]
    assert extractor.model == _LIVE_ENV_VALUES["GEMINI_MODEL"]
    assert continuity.model == _LIVE_ENV_VALUES["GEMINI_MODEL_LITE"]


def test_build_live_use_cases_shares_the_seamed_clients_across_use_cases(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The same `ClickHouseTrackerStore` instance backs every use case that
    needs a tracker -- the live-branch counterpart to CP-048's mock-sharing
    test above."""
    _clear_env(
        monkeypatch,
        CLEARCUT_MODE="live",
        GOOGLE_APPLICATION_CREDENTIALS=_write_fake_adc(tmp_path),
        **_LIVE_ENV_VALUES,
    )
    _forbid_sockets(monkeypatch)

    graph = _build_live_use_cases(ch_client=_FakeChClient(), vector_store=_FakeVectorStore())

    assert graph.analyze_script._tracker is graph.list_tracker_items._tracker
    assert graph.analyze_script._tracker is graph.resolve_finding._tracker


# ---------------------------------------------------------------------------
# Criterion 2: every credential, endpoint, and model id is read in
# composition.py only -- no adapter module reads the environment itself.
# ---------------------------------------------------------------------------


def test_no_adapter_module_reads_the_environment_directly() -> None:
    adapters_dir = Path(__file__).resolve().parents[2] / "src" / "clearcut" / "adapters"
    violations = [
        path
        for path in adapters_dir.rglob("*.py")
        if "os.environ" in path.read_text() or "os.getenv" in path.read_text()
    ]
    assert violations == [], f"adapter module(s) read the environment directly: {violations}"


# ---------------------------------------------------------------------------
# Criterion 5: a missing required variable fails at startup naming it, not
# at the first request.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("missing", sorted(_LIVE_ENV_VALUES))
def test_live_wiring_fails_at_startup_naming_a_missing_required_variable(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    present = {name: value for name, value in _LIVE_ENV_VALUES.items() if name != missing}
    _clear_env(monkeypatch, CLEARCUT_MODE="live", **present)
    with pytest.raises(RuntimeError, match=missing):
        create_app()


# ---------------------------------------------------------------------------
# Criterion 6 (D38): with no fakes injected and unreachable credentials,
# create_app() fails during construction, not on the first request.
# ---------------------------------------------------------------------------


def test_live_mode_with_unreachable_credentials_fails_during_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`CLICKHOUSE_HOST` names a reserved, never-resolving `.invalid` domain
    (RFC 2606) so DNS resolution fails fast and deterministically rather than
    hanging on a real connect timeout -- construction fails, and it fails
    naming ClickHouse, before `create_app()` ever returns an app."""
    _clear_env(monkeypatch, CLEARCUT_MODE="live", **_LIVE_ENV_VALUES)
    with pytest.raises(Exception, match="(?i)clickhouse"):
        create_app()


# ---------------------------------------------------------------------------
# CP-055: the Gemini 3 family answers only on the global endpoint.
#
# ADR 0002 pins gemini-3.7-flash and gemini-3.1-flash-lite, and composition
# built every client at us-central1, where both return 404 NOT_FOUND with
# "your project does not have access to it". Probed against the real API on
# 2026-09-03: every Gemini 3 model 404s at us-central1 and answers at global,
# while the 2.5 family answers at both. BigQuery and the embeddings must stay
# at us-central1, because that is where the dataset lives, so the two
# locations are genuinely different values rather than one constant.
# ---------------------------------------------------------------------------


def test_the_genai_client_is_built_on_the_global_endpoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_env(
        monkeypatch,
        CLEARCUT_MODE="live",
        GOOGLE_APPLICATION_CREDENTIALS=_write_fake_adc(tmp_path),
        **_LIVE_ENV_VALUES,
    )
    _forbid_sockets(monkeypatch)

    graph = _build_live_use_cases(ch_client=_FakeChClient(), vector_store=_FakeVectorStore())

    extractor = graph.analyze_script._extractor
    assert isinstance(extractor, GeminiSceneExtractor)
    # Reaching into `_api_client` because `genai.Client` exposes its location
    # nowhere public, and the port protocol the field is typed as declares only
    # the one method the adapter calls.
    location = cast(Any, extractor.client)._api_client.location
    assert location == "global", (
        "the Gemini 3 models ADR 0002 pins return 404 outside the global endpoint"
    )


def test_the_bigquery_dataset_location_is_not_the_genai_location() -> None:
    """Two locations, deliberately different.

    Collapsing them back into one constant breaks whichever service loses:
    the dataset does not exist at global, and the Gemini 3 models do not
    answer at us-central1.
    """
    assert _GCP_LOCATION == "us-central1"
    assert _GENAI_LOCATION == "global"


# ---------------------------------------------------------------------------
# CP-055: the ClickHouse console hands you a URL, the driver wants a hostname.
#
# `clickhouse_connect.get_client(host=...)` prepends the scheme itself, so
# pasting what the Connect panel shows produces
# `https://https://host:8443` and fails DNS resolution on the literal string
# "https". Seen on the first real connection attempt, 2026-09-03. Normalising
# here rather than asking every operator to reformat what the console gave them.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "configured",
    [
        "tnm.us-east1.gcp.clickhouse.cloud",
        "https://tnm.us-east1.gcp.clickhouse.cloud",
        "https://tnm.us-east1.gcp.clickhouse.cloud:8443",
        "http://tnm.us-east1.gcp.clickhouse.cloud:8443/",
        "  https://tnm.us-east1.gcp.clickhouse.cloud:8443  ",
    ],
)
def test_every_form_the_console_offers_reduces_to_the_bare_host(configured: str) -> None:
    assert _clickhouse_host(configured) == "tnm.us-east1.gcp.clickhouse.cloud"


def test_a_host_with_no_scheme_or_port_is_left_alone() -> None:
    """The already-correct value must survive untouched.

    A normaliser that rewrites valid input is worse than none: it turns one
    documented format into two, and only one of them is tested.
    """
    assert _clickhouse_host("localhost") == "localhost"


# ---------------------------------------------------------------------------
# CP-060: the SPA path has to survive being installed, not just imported.
#
# `_default_build_dir` walked three parents up from `composition.py`. In the
# repo that lands on the root and finds `web/dist`. Installed into
# site-packages it lands on `/usr/local/lib/python3.12`, and the deployed
# container served `{"error": "SPA build not found at
# /usr/local/lib/python3.12/web/dist"}`. Local runs never caught it because
# `pip install -e` leaves the package inside the repo.
# ---------------------------------------------------------------------------


def test_the_build_dir_is_found_from_the_working_directory(tmp_path: Path) -> None:
    """What the container has: sources at /app, package in site-packages."""
    (tmp_path / "web" / "dist").mkdir(parents=True)
    cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        assert _default_build_dir() == tmp_path / "web" / "dist"
    finally:
        os.chdir(cwd)


def test_the_build_dir_falls_back_to_the_package_layout(tmp_path: Path) -> None:
    """With no web/dist beside the process, the repo-relative path is still
    named -- so the error message points somewhere a developer recognises
    rather than at an empty temp directory."""
    cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        assert (
            _default_build_dir() == Path(composition.__file__).resolve().parents[2] / "web" / "dist"
        )
    finally:
        os.chdir(cwd)
