"""Unit tests for `GeminiSceneExtractor` (CP-007).

The injected client is a hand-written fake (AGENT.md Section 5): no
`unittest.mock`, no network. The fake records the exact request its caller
built, which is what proves the pinned `response_schema`, the mime type, and
the batching happen for real rather than by assumption.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import pytest
from google.genai import types

from clearcut.adapters.gemini.extractor import (
    ExtractionFailed,
    GeminiSceneExtractor,
    _GenerateContentModel,
    _GenerateContentResponse,
)
from clearcut.application.ports import SceneExtractor
from clearcut.domain.finding import Category, RiskLevel
from clearcut.domain.jurisdiction import jurisdiction_for
from clearcut.domain.script import Scene

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "gemini_findings.json"


@dataclass
class RecordedCall:
    model: str
    contents: list[str]
    config: types.GenerateContentConfig


@dataclass
class _FakeResponse:
    text: str | None


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
        if self._client.responses:
            return self._client.responses.pop(0)
        return _FakeResponse("[]")


@dataclass
class FakeGeminiClient:
    """Records every `generate_content` call; never touches the network."""

    responses: list[_FakeResponse] = field(default_factory=list)
    calls: list[RecordedCall] = field(default_factory=list)

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


def test_empty_scene_list_returns_empty_list_and_makes_no_client_calls() -> None:
    client = FakeGeminiClient()
    adapter = GeminiSceneExtractor(client=client, model="gemini-3.7-flash")

    findings = adapter.extract([], jurisdiction_for("US"))

    assert findings == []
    assert client.calls == []
