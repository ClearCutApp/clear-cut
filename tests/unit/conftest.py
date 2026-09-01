"""Shared fixtures for `tests/unit/` (CP-031).

`isolated_otel` is used by every test that needs its own tracer/meter
provider: OpenTelemetry's global providers are process-wide and refuse a
second `set_tracer_provider` / `set_meter_provider` call, so a test that
wants to read spans or metrics back through its own in-memory exporter must
first clear the two provider globals, then restore whatever was installed
before it once the test ends -- see `tests/unit/test_observability.py`'s
module docstring for the full reasoning.

`install_in_memory_telemetry` and `metric_attributes_by_name` are the setup
and read-back steps every adapter-level span/latency test repeats (CP-031
review, BLOCKING 2): `test_document_ai.py`, `test_vertex_search.py`,
`test_research.py`, `test_clickhouse_tracker.py` and `test_extractor.py` all
need them, past AGENT.md Section 4's "duplicate twice, extract on the third"
line.
"""

from collections.abc import Iterator

import opentelemetry.metrics._internal as otel_metrics_internal
import opentelemetry.trace as otel_trace
import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.util._once import Once


def install_in_memory_telemetry() -> tuple[InMemorySpanExporter, InMemoryMetricReader]:
    """Installs a fresh in-memory tracer/meter provider pair, so a test can
    read back the spans and metric points its own call recorded with no
    network call. Call under `isolated_otel`, which clears OpenTelemetry's
    process-wide provider globals first."""
    span_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    otel_trace.set_tracer_provider(tracer_provider)

    metric_reader = InMemoryMetricReader()
    otel_metrics_internal.set_meter_provider(MeterProvider(metric_readers=[metric_reader]))
    return span_exporter, metric_reader


def metric_attributes_by_name(
    metric_reader: InMemoryMetricReader,
) -> dict[str, list[dict[str, object]]]:
    """Each metric's data points, reduced to their attribute mappings -- the
    one shape CP-031's span-label assertions read."""
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


@pytest.fixture
def isolated_otel() -> Iterator[None]:
    saved_tracer_provider = otel_trace._TRACER_PROVIDER
    saved_tracer_once = otel_trace._TRACER_PROVIDER_SET_ONCE
    saved_meter_provider = otel_metrics_internal._METER_PROVIDER
    saved_meter_once = otel_metrics_internal._METER_PROVIDER_SET_ONCE
    otel_trace._TRACER_PROVIDER = None
    otel_trace._TRACER_PROVIDER_SET_ONCE = Once()
    otel_metrics_internal._METER_PROVIDER = None
    otel_metrics_internal._METER_PROVIDER_SET_ONCE = Once()
    try:
        yield
    finally:
        otel_trace._TRACER_PROVIDER = saved_tracer_provider
        otel_trace._TRACER_PROVIDER_SET_ONCE = saved_tracer_once
        otel_metrics_internal._METER_PROVIDER = saved_meter_provider
        otel_metrics_internal._METER_PROVIDER_SET_ONCE = saved_meter_once
