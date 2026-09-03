"""Unit tests for `GeminiSceneExtractor` (CP-007).

The injected client is a hand-written fake (AGENT.md Section 5): no
`unittest.mock`, no network. The fake records the exact request its caller
built, which is what proves the pinned `response_schema`, the mime type, and
the batching happen for real rather than by assumption.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import pytest
from google.genai import errors as genai_errors
from google.genai import types
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader, NumberDataPoint
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from clearcut.adapters.gemini.extractor import (
    ExtractionFailed,
    ExtractionUnavailable,
    GeminiSceneExtractor,
    _GenerateContentModel,
    _GenerateContentResponse,
)
from clearcut.application.ports import SceneExtractor
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.finding import Category, RiskLevel
from clearcut.domain.jurisdiction import jurisdiction_for
from clearcut.domain.script import Scene
from tests.unit.conftest import install_in_memory_telemetry, metric_attributes_by_name

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "gemini_findings.json"


@dataclass
class RecordedCall:
    model: str
    contents: list[str]
    config: types.GenerateContentConfig


@dataclass
class _FakeUsage:
    prompt_token_count: int | None
    candidates_token_count: int | None


@dataclass
class _FakeResponse:
    text: str | None
    usage_metadata: _FakeUsage | None = None


class _FakeModels:
    def __init__(self, client: "FakeGeminiClient") -> None:
        self._client = client

    def generate_content(
        self,
        *,
        model: str,
        contents: types.ContentListUnionDict,
        config: types.GenerateContentConfigOrDict | None = None,
    ) -> _GenerateContentResponse:
        assert isinstance(contents, list)
        assert isinstance(config, types.GenerateContentConfig)
        self._client.calls.append(
            RecordedCall(model=model, contents=cast(list[str], contents), config=config)
        )
        if self._client.error is not None:
            raise self._client.error
        if self._client.responses:
            return self._client.responses.pop(0)
        return _FakeResponse("[]")


@dataclass
class FakeGeminiClient:
    """Records every `generate_content` call; never touches the network."""

    responses: list[_FakeResponse] = field(default_factory=list)
    calls: list[RecordedCall] = field(default_factory=list)
    # Set to make `generate_content` raise instead of answering, so a test can
    # drive the transport failures the SDK call can produce.
    error: Exception | None = None

    def __post_init__(self) -> None:
        self.models: _GenerateContentModel = _FakeModels(self)


def _scene(number: int, page: int = 1, text: str = "A scene.") -> Scene:
    return Scene(
        number=number, heading="INT. ROOM - DAY", page_start=page, page_end=page, text=text
    )


checked: SceneExtractor = GeminiSceneExtractor(client=FakeGeminiClient(), model="gemini-3.7-flash")


def test_adapter_satisfies_scene_extractor_port() -> None:
    adapter = GeminiSceneExtractor(client=FakeGeminiClient(), model="gemini-3.7-flash")
    assert isinstance(adapter, SceneExtractor)


def test_pins_response_schema_mime_type_and_thinking_level_leaves_temperature_unset() -> None:
    client = FakeGeminiClient()
    adapter = GeminiSceneExtractor(client=client, model="gemini-3.7-flash")

    adapter.extract([_scene(1)], jurisdiction_for("US"))

    call = client.calls[0]
    assert isinstance(call.config, types.GenerateContentConfig)
    assert call.config.response_mime_type == "application/json"
    schema = call.config.response_schema
    assert isinstance(schema, types.Schema)
    assert schema.items is not None
    properties = schema.items.properties or {}
    for name in ("category", "ner_label", "raw_text", "risk_level", "required_document"):
        assert name in properties
    assert call.config.thinking_config is not None
    assert call.config.thinking_config.thinking_level is not None
    assert call.config.temperature is None


def test_batches_at_most_eight_scenes_per_gemini_call() -> None:
    client = FakeGeminiClient()
    adapter = GeminiSceneExtractor(client=client, model="gemini-3.7-flash")
    scenes = [_scene(number) for number in range(1, 18)]

    adapter.extract(scenes, jurisdiction_for("US"))

    assert len(client.calls) == 3
    assert [len(call.contents) for call in client.calls] == [8, 8, 1]


def test_derives_category_from_ner_label_ignoring_the_models_own_category_string() -> None:
    client = FakeGeminiClient(responses=[_FakeResponse(FIXTURE_PATH.read_text())])
    adapter = GeminiSceneExtractor(client=client, model="gemini-3.7-flash")
    scene = _scene(4, page=10)

    findings = adapter.extract([scene], jurisdiction_for("US"))

    assert len(findings) == 2
    assert findings[0].category == Category.INDUSTRIAL_PROPERTY
    assert findings[1].category == Category.COPYRIGHT_WORKS
    assert {finding.category for finding in findings}.isdisjoint({Category.SPECIAL_SYMBOLS})
    assert findings[0].risk_level == RiskLevel.MEDIUM
    assert findings[0].scene_number == 4
    assert findings[0].page == 10


def test_raises_extraction_failed_for_an_unrecognized_ner_label() -> None:
    bad_response = _FakeResponse(
        '[{"scene_number": 1, "category": "POLICY", "ner_label": "NOT_A_REAL_TAG", '
        '"raw_text": "x", "risk_level": "LOW", "required_document": "none"}]'
    )
    client = FakeGeminiClient(responses=[bad_response])
    adapter = GeminiSceneExtractor(client=client, model="gemini-3.7-flash")

    with pytest.raises(ExtractionFailed, match="NOT_A_REAL_TAG"):
        adapter.extract([_scene(1)], jurisdiction_for("US"))


def test_generate_content_call_carries_the_model_the_adapter_was_constructed_with() -> None:
    client = FakeGeminiClient()
    model = "model-injected-at-construction"
    adapter = GeminiSceneExtractor(client=client, model=model)

    adapter.extract([_scene(1)], jurisdiction_for("US"))

    assert client.calls[0].model == model


def test_empty_scene_list_returns_empty_list_and_makes_no_client_calls() -> None:
    client = FakeGeminiClient()
    adapter = GeminiSceneExtractor(client=client, model="gemini-3.7-flash")

    findings = adapter.extract([], jurisdiction_for("US"))

    assert findings == []
    assert client.calls == []


# ---------------------------------------------------------------------------
# CP-031 (ADR 0008, SDD Section 6): the "extract" span carries the Gemini
# model name and the prompt/output token counts read from the response's own
# usage metadata, and `clearcut_gemini_tokens_total` records them split by
# token type -- both driven from the fake response's `usage_metadata`, never
# recounted from the response text, so a mutant that recounts locally fails.
# ---------------------------------------------------------------------------


@dataclass
class _MetricPoint:
    attributes: dict[str, object]
    value: int | float


def _data_points_by_metric_name(
    metric_reader: InMemoryMetricReader,
) -> dict[str, list[_MetricPoint]]:
    data = metric_reader.get_metrics_data()
    points_by_name: dict[str, list[_MetricPoint]] = {}
    if data is None:
        return points_by_name
    for resource_metrics in data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                for point in metric.data.data_points:
                    attributes: dict[str, object] = dict(point.attributes or {})
                    value = point.value if isinstance(point, NumberDataPoint) else 0.0
                    points_by_name.setdefault(metric.name, []).append(
                        _MetricPoint(attributes, value)
                    )
    return points_by_name


def test_extract_span_and_counter_carry_token_counts_from_usage_metadata(
    isolated_otel: None,
) -> None:
    span_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    metric_reader = InMemoryMetricReader()
    metrics.set_meter_provider(MeterProvider(metric_readers=[metric_reader]))

    response = _FakeResponse(
        FIXTURE_PATH.read_text(),
        usage_metadata=_FakeUsage(prompt_token_count=123, candidates_token_count=45),
    )
    client = FakeGeminiClient(responses=[response])
    adapter = GeminiSceneExtractor(client=client, model="gemini-3.7-flash")

    adapter.extract([_scene(4, page=10)], jurisdiction_for("US"))

    spans = [span for span in span_exporter.get_finished_spans() if span.name == "extract"]
    assert len(spans) == 1
    attributes = spans[0].attributes
    assert attributes is not None
    assert attributes.get("gemini_model") == "gemini-3.7-flash"
    assert attributes.get("prompt_tokens") == 123
    assert attributes.get("output_tokens") == 45

    points_by_name = _data_points_by_metric_name(metric_reader)
    tokens = points_by_name["clearcut_gemini_tokens_total"]
    by_type = {point.attributes["token_type"]: point for point in tokens}
    assert by_type["prompt"].value == 123
    assert by_type["output"].value == 45
    assert all(point.attributes["model"] == "gemini-3.7-flash" for point in tokens)


def test_extract_opens_an_extract_span_and_records_stage_latency(isolated_otel: None) -> None:
    """CP-031 (ADR 0008, SDD Section 6): the `extractor.py:174` latency
    record (CP-031 review, BLOCKING 2) had no test that would fail without
    it -- the test above this one covers the span's token attributes and the
    Gemini token counter, not `clearcut_stage_latency_ms`."""
    span_exporter, metric_reader = install_in_memory_telemetry()
    client = FakeGeminiClient()
    adapter = GeminiSceneExtractor(client=client, model="gemini-3.7-flash")

    adapter.extract([_scene(1)], jurisdiction_for("US"))

    spans = [span for span in span_exporter.get_finished_spans() if span.name == "extract"]
    assert len(spans) == 1

    latency_points = metric_attributes_by_name(metric_reader)["clearcut_stage_latency_ms"]
    assert latency_points
    assert all(point["stage"] == "extract" for point in latency_points)


# --- CP-056: what the SDK can raise, and what must cross the port instead ----
#
# `_extract_batch` called `generate_content` bare until 2026-09-03, so an
# upstream outage, a non-JSON body, or a model naming a scene outside its own
# batch all reached `routes.py`'s generic handler and became a 500 reading
# "internal error". Each test below fails without the translation.


def _extractor(client: FakeGeminiClient) -> GeminiSceneExtractor:
    return GeminiSceneExtractor(client=client, model="gemini-3.7-flash")


def test_an_api_error_becomes_extraction_unavailable_not_a_bare_api_error() -> None:
    client = FakeGeminiClient(error=genai_errors.ServerError(503, {"error": "unavailable"}))

    with pytest.raises(SourceUnavailable) as caught:
        _extractor(client).extract([_scene(1)], jurisdiction_for("AR"))

    assert isinstance(caught.value, ExtractionUnavailable)
    assert not isinstance(caught.value, genai_errors.APIError)


def test_a_response_that_is_not_json_becomes_extraction_unavailable() -> None:
    client = FakeGeminiClient(responses=[_FakeResponse("I could not answer that.")])

    with pytest.raises(ExtractionUnavailable):
        _extractor(client).extract([_scene(1)], jurisdiction_for("AR"))


def test_a_scene_number_outside_the_batch_becomes_extraction_unavailable() -> None:
    """The likeliest of the three: it needs a hallucination, not an outage."""
    client = FakeGeminiClient(
        responses=[
            _FakeResponse(
                json.dumps(
                    [
                        {
                            "scene_number": 99,
                            "ner_label": "BRAND",
                            "raw_text": "a Ferrari Testarossa",
                            "risk_level": "HIGH",
                            "required_document": "Trademark clearance",
                        }
                    ]
                )
            )
        ]
    )

    with pytest.raises(ExtractionUnavailable) as caught:
        _extractor(client).extract([_scene(1)], jurisdiction_for("AR"))

    assert "99" in str(caught.value)


def test_a_response_missing_a_required_field_becomes_extraction_unavailable() -> None:
    client = FakeGeminiClient(
        responses=[_FakeResponse(json.dumps([{"scene_number": 1, "ner_label": "BRAND"}]))]
    )

    with pytest.raises(ExtractionUnavailable):
        _extractor(client).extract([_scene(1)], jurisdiction_for("AR"))
