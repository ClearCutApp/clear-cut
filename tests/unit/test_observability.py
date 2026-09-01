"""Unit tests for CP-031's OpenTelemetry instrumentation (ADR 0008,
docs/plan/sdd.md Section 6): the tracer/meter providers `create_app()`
configures once, the five pipeline-stage spans, and the four Section 6
metrics.

Every assertion reads spans and metrics back through an in-memory exporter
or an in-memory metric reader -- no Grafana Cloud account is needed to run
or review this file (CP-031's own Notes: the live-arrival check is a
different, hand-run SDD Section 8 check).

OpenTelemetry's tracer and meter providers are process-wide globals that
refuse a second `set_tracer_provider` / `set_meter_provider` call -- they log
a warning and keep the first one installed. `composition.py`'s own
`_configure_telemetry` relies on exactly that shape so a second
`create_app()` call in the same process is a safe no-op (every test in
`test_composition.py` after the first one makes such a call). The same shape
means a test here that wants its own exporter must install its own provider
*first*: `_configure_telemetry` then finds one already installed and leaves
it alone, so `create_app()` ends up recording into the exporter this file
planted. `conftest.py`'s `isolated_otel` fixture clears the two provider
globals before a test that needs a fresh install and restores whatever was
installed before it once the test ends, so nothing here leaks into a test in
another file.
"""

import os
import socket
from collections.abc import Sequence

import pytest
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from clearcut import composition
from clearcut.composition import create_app

_ANALYZE_BODY = {
    "project_id": "demo-project",
    "jurisdiction_code": "AR",
    "gcs_uri": "gs://clearcut-demo/planted-script-v1.pdf",
    "version": 1,
}

_FIVE_STAGE_NAMES = frozenset({"ingest", "extract", "ground", "research", "track"})


def _clear_env(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    monkeypatch.setattr(os, "environ", dict(overrides))


def _install_in_memory_providers() -> tuple[InMemorySpanExporter, InMemoryMetricReader]:
    span_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    metric_reader = InMemoryMetricReader()
    metrics.set_meter_provider(MeterProvider(metric_readers=[metric_reader]))
    return span_exporter, metric_reader


class _RaisingSpanExporter(SpanExporter):
    """A hand-written fake span exporter (AGENT.md Section 5) whose
    `export` always raises, proving CP-031's second failure path: a
    telemetry backend that is down must never take the pipeline down with
    it."""

    def __init__(self) -> None:
        self.calls: list[int] = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.calls.append(1)
        raise RuntimeError("simulated OTLP export failure")


# ---------------------------------------------------------------------------
# Criterion 1: the OTLP exporters read OTEL_EXPORTER_OTLP_ENDPOINT and
# OTEL_EXPORTER_OTLP_HEADERS from the environment, opening no socket.
# ---------------------------------------------------------------------------


def _set_otlp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """`monkeypatch.setenv` mutates the real `os.environ` mapping in place,
    which both `composition.py`'s own `os.environ` lookups and the OTLP
    exporters' `from os import environ` reference see -- unlike
    `_clear_env`'s whole-object replacement, which only the former sees
    (the module-level `environ` name the exporter packages import keeps
    pointing at the original mapping object)."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://otlp-gateway.example.com")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "Authorization=Basic dGVzdDp0ZXN0")


def test_span_exporter_reads_endpoint_and_headers_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_otlp_env(monkeypatch)
    exporter = composition._span_exporter()
    assert exporter is not None
    assert exporter._endpoint == "https://otlp-gateway.example.com/v1/traces"
    assert exporter._headers == {"authorization": "Basic dGVzdDp0ZXN0"}


def test_metric_exporter_reads_endpoint_and_headers_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_otlp_env(monkeypatch)
    exporter = composition._metric_exporter()
    assert exporter is not None
    assert exporter._endpoint == "https://otlp-gateway.example.com/v1/metrics"
    assert exporter._headers == {"authorization": "Basic dGVzdDp0ZXN0"}


def test_exporters_open_no_socket_during_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_otlp_env(monkeypatch)

    def _blocked(self: socket.socket, *args: object, **kwargs: object) -> None:
        raise AssertionError("socket connected during exporter construction")

    monkeypatch.setattr(socket.socket, "connect", _blocked)

    assert composition._span_exporter() is not None
    assert composition._metric_exporter() is not None


def test_create_app_installs_a_batch_span_processor_and_a_metric_reader_wired_to_env(
    monkeypatch: pytest.MonkeyPatch, isolated_otel: None
) -> None:
    """Criterion 1, literally: calls `create_app()` -- not the private
    `_span_exporter()` / `_metric_exporter()` helpers alone (the two tests
    above this one) -- and asserts what `create_app()` actually installs.
    Kills all four mutants a reviewer found surviving: deleting the
    `_configure_telemetry()` call at `composition.py:171`; replacing
    `_configure_telemetry`'s body with `return` (`composition.py:84`); never
    running `tracer_provider.add_span_processor(BatchSpanProcessor(...))`
    (`composition.py:99`); and forcing `metric_readers = []`
    (`composition.py:103`)."""
    _set_otlp_env(monkeypatch)
    monkeypatch.setenv("CLEARCUT_MODE", "mock")

    create_app()

    tracer_provider = trace.get_tracer_provider()
    assert isinstance(tracer_provider, TracerProvider)
    span_processors = tracer_provider._active_span_processor._span_processors
    batch_processors = [
        processor for processor in span_processors if isinstance(processor, BatchSpanProcessor)
    ]
    assert len(batch_processors) == 1
    span_exporter = batch_processors[0].span_exporter
    assert span_exporter._endpoint == "https://otlp-gateway.example.com/v1/traces"
    assert span_exporter._headers == {"authorization": "Basic dGVzdDp0ZXN0"}

    meter_provider = metrics.get_meter_provider()
    assert isinstance(meter_provider, MeterProvider)
    assert len(meter_provider._metric_readers) == 1
    metric_reader = meter_provider._metric_readers[0]
    assert isinstance(metric_reader, PeriodicExportingMetricReader)
    metric_exporter = metric_reader._exporter
    assert isinstance(metric_exporter, OTLPMetricExporter)
    assert metric_exporter._endpoint == "https://otlp-gateway.example.com/v1/metrics"
    assert metric_exporter._headers == {"authorization": "Basic dGVzdDp0ZXN0"}


# ---------------------------------------------------------------------------
# Criterion 8: with OTEL_EXPORTER_OTLP_ENDPOINT unset, create_app() returns a
# working app and the pipeline runs unchanged -- spans and metrics go
# nowhere, no exception, no network call.
# ---------------------------------------------------------------------------


def test_exporters_are_none_when_endpoint_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    assert composition._span_exporter() is None
    assert composition._metric_exporter() is None


def test_create_app_works_and_opens_no_socket_with_endpoint_unset(
    monkeypatch: pytest.MonkeyPatch, isolated_otel: None
) -> None:
    _clear_env(monkeypatch, CLEARCUT_MODE="mock")

    def _blocked(self: socket.socket, *args: object, **kwargs: object) -> None:
        raise AssertionError("socket connected with OTEL_EXPORTER_OTLP_ENDPOINT unset")

    monkeypatch.setattr(socket.socket, "connect", _blocked)

    client = create_app().test_client()
    response = client.post("/api/analyze", json=_ANALYZE_BODY)

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Criterion 2: one span per pipeline stage, named exactly ingest, extract,
# ground, research, track, sharing one trace id, in CLEARCUT_MODE=mock over
# CP-043's demo adapters.
# ---------------------------------------------------------------------------


def test_five_pipeline_stage_spans_appear_and_share_one_trace_id(
    monkeypatch: pytest.MonkeyPatch, isolated_otel: None
) -> None:
    span_exporter, _ = _install_in_memory_providers()
    _clear_env(monkeypatch, CLEARCUT_MODE="mock")

    client = create_app().test_client()
    response = client.post("/api/analyze", json=_ANALYZE_BODY)
    assert response.status_code == 200

    spans = span_exporter.get_finished_spans()
    names = {span.name for span in spans}
    assert _FIVE_STAGE_NAMES <= names

    trace_ids = {span.context.trace_id for span in spans if span.name in _FIVE_STAGE_NAMES}
    assert len(trace_ids) == 1


def test_root_span_carries_script_id(monkeypatch: pytest.MonkeyPatch, isolated_otel: None) -> None:
    span_exporter, _ = _install_in_memory_providers()
    _clear_env(monkeypatch, CLEARCUT_MODE="mock")

    client = create_app().test_client()
    response = client.post("/api/analyze", json=_ANALYZE_BODY)
    script_id = response.get_json()["script_id"]

    root_spans = [
        span for span in span_exporter.get_finished_spans() if span.name not in _FIVE_STAGE_NAMES
    ]
    assert len(root_spans) == 1
    assert root_spans[0].attributes is not None
    assert root_spans[0].attributes.get("script_id") == script_id


# ---------------------------------------------------------------------------
# Criteria 4 and 6: the four SDD Section 6 metrics record one point per
# metric with their labels present in CLEARCUT_MODE=mock; the Gemini token
# counter records nothing since no model ran.
# ---------------------------------------------------------------------------


def _data_points_by_metric_name(
    metric_reader: InMemoryMetricReader,
) -> dict[str, list[dict[str, object]]]:
    """Each metric's data points, reduced to their attribute mappings: the
    four instruments record a mix of histogram and number data points, so
    this collapses that union to the one shape every test here actually
    reads."""
    data = metric_reader.get_metrics_data()
    points_by_name: dict[str, list[dict[str, object]]] = {}
    if data is None:
        return points_by_name
    for resource_metrics in data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                for point in metric.data.data_points:
                    attributes: dict[str, object] = dict(point.attributes or {})
                    points_by_name.setdefault(metric.name, []).append(attributes)
    return points_by_name


def test_four_metrics_record_one_point_each_with_labels_in_mock_mode(
    monkeypatch: pytest.MonkeyPatch, isolated_otel: None
) -> None:
    _, metric_reader = _install_in_memory_providers()
    _clear_env(monkeypatch, CLEARCUT_MODE="mock")

    client = create_app().test_client()
    response = client.post("/api/analyze", json=_ANALYZE_BODY)
    assert response.status_code == 200

    points_by_name = _data_points_by_metric_name(metric_reader)

    latency_points = points_by_name["clearcut_stage_latency_ms"]
    assert latency_points
    stages = {point["stage"] for point in latency_points}
    assert stages == {"ingest", "extract", "ground", "research", "track"}

    assert points_by_name["clearcut_findings_total"]
    for point in points_by_name["clearcut_findings_total"]:
        assert "risk_level" in point
        assert "category" in point

    assert points_by_name["clearcut_tracker_items"]
    for point in points_by_name["clearcut_tracker_items"]:
        assert "state" in point


def test_gemini_tokens_total_has_no_points_in_mock_mode(
    monkeypatch: pytest.MonkeyPatch, isolated_otel: None
) -> None:
    _, metric_reader = _install_in_memory_providers()
    _clear_env(monkeypatch, CLEARCUT_MODE="mock")

    client = create_app().test_client()
    client.post("/api/analyze", json=_ANALYZE_BODY)

    points_by_name = _data_points_by_metric_name(metric_reader)
    assert points_by_name.get("clearcut_gemini_tokens_total", []) == []


# ---------------------------------------------------------------------------
# Criterion 9: an exporter that raises never reaches a use case.
# ---------------------------------------------------------------------------


def test_a_raising_span_exporter_never_breaks_the_analyze_call(
    monkeypatch: pytest.MonkeyPatch, isolated_otel: None
) -> None:
    raising_exporter = _RaisingSpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(raising_exporter))
    trace.set_tracer_provider(tracer_provider)
    metrics.set_meter_provider(MeterProvider(metric_readers=[]))

    _clear_env(monkeypatch, CLEARCUT_MODE="mock")
    client = create_app().test_client()

    response = client.post("/api/analyze", json=_ANALYZE_BODY)

    assert response.status_code == 200
    assert raising_exporter.calls  # proves the exporter really was invoked and really did raise
