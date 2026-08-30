"""Unit tests for `GeminiContinuityCheck` (CP-022).

The injected client is a hand-written fake (AGENT.md Section 5): no
`unittest.mock`, no network. The fake records the exact request its caller
built, which is what proves the pinned `response_schema` and the empty-facts
short circuit happen for real rather than by assumption.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import pytest
from google.genai import types

from clearcut.adapters.gemini.continuity import (
    ContinuityCheckFailed,
    GeminiContinuityCheck,
    _GenerateContentModel,
    _GenerateContentResponse,
)
from clearcut.application.ports import ContinuityCheck
from clearcut.domain.bible import BibleFact, FactKind
from clearcut.domain.finding import Category
from clearcut.domain.script import Scene

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "continuity_response.json"


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
        return _FakeResponse('{"contradicts": null}')


@dataclass
class FakeGeminiClient:
    """Records every `generate_content` call; never touches the network."""

    responses: list[_FakeResponse] = field(default_factory=list)
    calls: list[RecordedCall] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.models: _GenerateContentModel = _FakeModels(self)


def _scene(number: int = 1, page: int = 1, text: str = "A scene.") -> Scene:
    return Scene(
        number=number, heading="INT. ROOM - DAY", page_start=page, page_end=page, text=text
    )


def _fact(fact_id: str = "FACT-001", kind: FactKind = FactKind.LORE) -> BibleFact:
    return BibleFact(
        fact_id=fact_id, kind=kind, text="The father lives abroad.", source="Bible p. 4"
    )


checked: ContinuityCheck = GeminiContinuityCheck(
    client=FakeGeminiClient(), model="gemini-3.1-flash-lite"
)


def test_adapter_satisfies_continuity_check_port() -> None:
    adapter = GeminiContinuityCheck(client=FakeGeminiClient(), model="gemini-3.1-flash-lite")
    assert isinstance(adapter, ContinuityCheck)


def test_pins_response_schema_and_mime_type_leaves_temperature_unset() -> None:
    client = FakeGeminiClient()
    adapter = GeminiContinuityCheck(client=client, model="gemini-3.1-flash-lite")

    adapter.check(_scene(), [_fact()])

    call = client.calls[0]
    assert isinstance(call.config, types.GenerateContentConfig)
    assert call.config.response_mime_type == "application/json"
    schema = call.config.response_schema
    assert isinstance(schema, types.Schema)
    properties = schema.properties or {}
    for name in ("contradicts", "category", "raw_text", "risk_level", "required_document"):
        assert name in properties
    assert call.config.temperature is None


def test_scene_contradicting_a_lore_fact_yields_continuity_finding() -> None:
    client = FakeGeminiClient(responses=[_FakeResponse(FIXTURE_PATH.read_text())])
    adapter = GeminiContinuityCheck(client=client, model="gemini-3.1-flash-lite")
    fact = _fact(fact_id="FACT-007", kind=FactKind.LORE)
    scene = _scene(number=4, page=8)

    finding = adapter.check(scene, [fact])

    assert finding is not None
    assert finding.category == Category.CONTINUITY
    assert finding.ner_label is None
    assert finding.contradicts == "FACT-007"
    assert finding.scene_number == 4
    assert finding.page == 8


def test_scene_violating_a_policy_fact_yields_policy_finding() -> None:
    response = _FakeResponse(
        '{"contradicts": "FACT-009", "category": "POLICY", '
        '"raw_text": "He lights a cigarette.", "risk_level": "MEDIUM", '
        '"required_document": "Policy exception sign-off"}'
    )
    client = FakeGeminiClient(responses=[response])
    adapter = GeminiContinuityCheck(client=client, model="gemini-3.1-flash-lite")
    fact = _fact(fact_id="FACT-009", kind=FactKind.POLICY)

    finding = adapter.check(_scene(), [fact])

    assert finding is not None
    assert finding.category == Category.POLICY
    assert finding.ner_label is None
    assert finding.contradicts == "FACT-009"


def test_scene_contradicting_nothing_returns_none() -> None:
    client = FakeGeminiClient(responses=[_FakeResponse('{"contradicts": null}')])
    adapter = GeminiContinuityCheck(client=client, model="gemini-3.1-flash-lite")

    finding = adapter.check(_scene(), [_fact()])

    assert finding is None
    assert len(client.calls) == 1


def test_raises_continuity_check_failed_for_a_category_outside_continuity_and_policy() -> None:
    response = _FakeResponse(
        '{"contradicts": "FACT-001", "category": "COPYRIGHT_WORKS", '
        '"raw_text": "x", "risk_level": "LOW", "required_document": "none"}'
    )
    client = FakeGeminiClient(responses=[response])
    adapter = GeminiContinuityCheck(client=client, model="gemini-3.1-flash-lite")

    with pytest.raises(ContinuityCheckFailed, match="COPYRIGHT_WORKS"):
        adapter.check(_scene(), [_fact()])


def test_generate_content_call_carries_the_model_the_adapter_was_constructed_with() -> None:
    client = FakeGeminiClient()
    model = "model-injected-at-construction"
    adapter = GeminiContinuityCheck(client=client, model=model)

    adapter.check(_scene(), [_fact()])

    assert client.calls[0].model == model


def test_request_contents_carry_the_scene_text_and_every_facts_id() -> None:
    client = FakeGeminiClient()
    adapter = GeminiContinuityCheck(client=client, model="gemini-3.1-flash-lite")
    scene = _scene(number=4, page=8, text="INT. KITCHEN - DAY. He lights a cigarette.")
    facts = [_fact(fact_id="FACT-007"), _fact(fact_id="FACT-009")]

    adapter.check(scene, facts)

    contents = client.calls[0].contents
    assert any(scene.text in item for item in contents)
    for fact in facts:
        assert any(fact.fact_id in item for item in contents)


def test_empty_facts_returns_none_and_makes_no_client_calls() -> None:
    client = FakeGeminiClient()
    adapter = GeminiContinuityCheck(client=client, model="gemini-3.1-flash-lite")

    finding = adapter.check(_scene(), [])

    assert finding is None
    assert client.calls == []
