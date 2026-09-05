"""Grafana Cloud receipt for CP-058.

In-process exporters do not count: this queries Grafana's HTTP API for the
four-panel dashboard, the five stage spans under one trace, and a non-zero
`clearcut_gemini_tokens_total` prompt series for `gemini-3.7-flash`.

Skips without GRAFANA_URL and GRAFANA_TOKEN. Those are a Grafana service
account, not the OTLP write pair already in `.env`.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import pytest
from google import genai
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from clearcut.adapters.gemini.extractor import GeminiSceneExtractor
from clearcut.domain.jurisdiction import jurisdiction_for
from clearcut.domain.script import Scene
from tests.live.conftest import env, requires

_STAGES = ("ingest", "extract", "ground", "research", "track")
_PANEL_TITLES = (
    "Stage latency",
    "Tokens per model",
    "Findings by severity",
    "Tracker items by state",
)
_DASHBOARD_UID = "clearcut-pipeline"
_TOKEN_QUERY = 'sum(clearcut_gemini_tokens_total{model="gemini-3.7-flash",token_type="prompt"})'
_TRACEQL = (
    '{ name = "ingest" } && { name = "extract" } && { name = "ground" }'
    ' && { name = "research" } && { name = "track" }'
)
_SCENE = Scene(
    number=1,
    heading="INT. BAR - DAY",
    page_start=1,
    page_end=1,
    text=(
        "INT. BAR - DAY\n"
        "A neon Quilmes sign glows over the counter. MARA slides a bottle of\n"
        'Coca-Cola across the bar while "Hotel California" plays on the radio.'
    ),
)
_RESOURCE = Resource.create({"service.name": "clearcut"})


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {env('GRAFANA_TOKEN')}",
        "Accept": "application/json",
    }


def _base() -> str:
    return env("GRAFANA_URL").rstrip("/")


def _get(path: str, params: dict[str, str] | None = None) -> httpx.Response:
    return httpx.get(
        f"{_base()}{path}",
        headers=_headers(),
        params=params,
        timeout=30.0,
    )


def _datasource_uid(kind: str) -> str:
    response = _get("/api/datasources")
    response.raise_for_status()
    payload = response.json()
    assert isinstance(payload, list), payload
    matches = [row for row in payload if row.get("type") == kind]
    assert matches, f"no {kind} datasource on this Grafana stack"
    return str(matches[0]["uid"])


def _proxy(uid: str, path: str, params: dict[str, str]) -> dict[str, Any]:
    response = _get(f"/api/datasources/proxy/uid/{uid}{path}", params)
    response.raise_for_status()
    payload = response.json()
    assert isinstance(payload, dict), payload
    return payload


def _install_otlp_metrics() -> PeriodicExportingMetricReader:
    reader = PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=500)
    metrics.set_meter_provider(MeterProvider(metric_readers=[reader], resource=_RESOURCE))
    return reader


def _export_stage_spans() -> None:
    exporter = OTLPSpanExporter()
    provider = TracerProvider(resource=_RESOURCE)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("cp058")
    with tracer.start_as_current_span("clearcut.analyze"):
        for name in _STAGES:
            with tracer.start_as_current_span(name):
                pass
    provider.force_flush()
    provider.shutdown()


def _wait_until(probe: Any, timeout: float = 90.0) -> Any:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = probe()
        if last:
            return last
        time.sleep(2)
    return last


@pytest.mark.live
@requires("GRAFANA_URL", "GRAFANA_TOKEN")
def test_grafana_dashboard_has_the_four_section_10_panels() -> None:
    response = _get(f"/api/dashboards/uid/{_DASHBOARD_UID}")
    assert response.status_code != 404, (
        "dashboard uid=clearcut-pipeline is not on this Grafana stack; "
        "run .venv/bin/python infra/provision_grafana_dashboard.py"
    )
    response.raise_for_status()
    dashboard = response.json()["dashboard"]
    titles = [panel["title"] for panel in dashboard["panels"]]
    assert titles == list(_PANEL_TITLES)


@pytest.mark.live
@requires("GRAFANA_URL", "GRAFANA_TOKEN", "OTEL_EXPORTER_OTLP_ENDPOINT")
def test_five_stage_spans_share_one_trace_in_grafana(isolated_otel: None) -> None:
    _export_stage_spans()
    uid = _datasource_uid("tempo")

    def _traces() -> list[Any]:
        payload = _proxy(uid, "/api/search", {"q": _TRACEQL, "limit": "20"})
        traces = payload.get("traces") or []
        return traces if isinstance(traces, list) else []

    traces = _wait_until(_traces)
    assert traces, (
        f"Tempo returned no trace matching {_TRACEQL!r} after OTLP export; "
        "the write may have landed and the query token cannot read it"
    )


@pytest.mark.live
@requires(
    "GRAFANA_URL",
    "GRAFANA_TOKEN",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "GOOGLE_CLOUD_PROJECT",
    "GEMINI_MODEL",
)
def test_gemini_prompt_tokens_are_nonzero_in_grafana(isolated_otel: None) -> None:
    reader = _install_otlp_metrics()
    extractor = GeminiSceneExtractor(
        client=genai.Client(
            vertexai=True,
            project=env("GOOGLE_CLOUD_PROJECT"),
            location="global",
        ),
        model="gemini-3.7-flash",
    )
    assert extractor.extract([_SCENE], jurisdiction_for("AR"))
    reader.force_flush()
    reader.shutdown()

    uid = _datasource_uid("prometheus")

    def _prompt_tokens() -> float:
        payload = _proxy(uid, "/api/v1/query", {"query": _TOKEN_QUERY})
        result = (payload.get("data") or {}).get("result") or []
        if not result:
            return 0.0
        value = result[0].get("value") or [0, "0"]
        return float(value[1])

    total = _wait_until(lambda: _prompt_tokens() > 0)
    assert total, (
        "clearcut_gemini_tokens_total prompt series for gemini-3.7-flash "
        "is zero or missing in Grafana; a zero means mock mode or the "
        "query token cannot read Mimir"
    )
