"""Tests for the Vertex AI Search grounding adapter (CP-009, ADR 0005)."""

import json
from pathlib import Path

import pytest
from google.genai import types

from clearcut.adapters.gcp.vertex_search import (
    NoGroundedSource,
    VertexSearchGrounding,
)
from clearcut.application.ports import GroundedAnswer, LegalGrounding
from clearcut.domain.jurisdiction import Jurisdiction, jurisdiction_for

_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "vertex_grounded_answer.json"
_DATA_STORE_ID = (
    "projects/clearcut-hack/locations/us/collections/default_collection/"
    "dataStores/clearcut-legal-corpus"
)


class FakeVertexSearchClient:
    """Hand-written fake standing in for `google.genai.Client.models`."""

    def __init__(self, response: types.GenerateContentResponse) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    def generate_content(
        self,
        *,
        model: str,
        contents: str,
        config: types.GenerateContentConfig,
    ) -> types.GenerateContentResponse:
        self.calls.append({"model": model, "contents": contents, "config": config})
        return self._response


def _load_fixture_response() -> types.GenerateContentResponse:
    data = json.loads(_FIXTURE.read_text())
    return types.GenerateContentResponse.model_validate(data)


def _response_without_grounding_chunks() -> types.GenerateContentResponse:
    return types.GenerateContentResponse.model_validate(
        {
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": "An answer with no source."}]},
                    "groundingMetadata": {"groundingChunks": []},
                }
            ]
        }
    )


def test_adapter_implements_legal_grounding_port() -> None:
    fake = FakeVertexSearchClient(_load_fixture_response())
    adapter = VertexSearchGrounding(fake, _DATA_STORE_ID)
    checked: LegalGrounding = adapter
    assert isinstance(checked, LegalGrounding)


def test_query_for_ar_jurisdiction_sends_filter_derived_from_corpus_prefix() -> None:
    fake = FakeVertexSearchClient(_load_fixture_response())
    adapter = VertexSearchGrounding(fake, _DATA_STORE_ID)

    adapter.ground("Can I use a Ferrari logo?", jurisdiction_for("AR"))

    assert len(fake.calls) == 1
    config = fake.calls[0]["config"]
    assert isinstance(config, types.GenerateContentConfig)
    assert config.tools is not None
    tool = config.tools[0]
    assert isinstance(tool, types.Tool)
    assert tool.retrieval is not None
    search = tool.retrieval.vertex_ai_search
    assert search is not None
    assert search.filter == 'jurisdiction: ANY("argentina")'


def test_fixture_response_with_grounding_chunks_returns_citations() -> None:
    fake = FakeVertexSearchClient(_load_fixture_response())
    adapter = VertexSearchGrounding(fake, _DATA_STORE_ID)

    answer = adapter.ground("What does Ley 11.723 say about film use?", jurisdiction_for("AR"))

    assert isinstance(answer, GroundedAnswer)
    assert answer.text == (
        "Under Argentine law, using a copyrighted work in a film "
        "without a license infringes Ley 11.723."
    )
    assert len(answer.citations) == 1
    citation = answer.citations[0]
    assert citation.uri == "gs://clearcut-legal-corpus/argentina/ley-11723.pdf"
    assert citation.title == "Ley 11.723 - Regimen Legal de la Propiedad Intelectual"


def test_response_without_grounding_chunks_raises_no_grounded_source() -> None:
    fake = FakeVertexSearchClient(_response_without_grounding_chunks())
    adapter = VertexSearchGrounding(fake, _DATA_STORE_ID)

    with pytest.raises(NoGroundedSource) as excinfo:
        adapter.ground("An ungrounded question.", jurisdiction_for("AR"))

    # The answer text must never surface without a citation trail: the
    # exception carries only the query, never the model's uncited text.
    assert excinfo.value.query == "An ungrounded question."
    assert "An answer with no source." not in str(excinfo.value)


def test_blank_corpus_prefix_raises_value_error_before_any_client_call() -> None:
    fake = FakeVertexSearchClient(_load_fixture_response())
    adapter = VertexSearchGrounding(fake, _DATA_STORE_ID)
    blank_jurisdiction = Jurisdiction(code="ZZ", display_name="Nowhere", corpus_prefix="   ")

    with pytest.raises(ValueError):
        adapter.ground("Any question.", blank_jurisdiction)

    assert fake.calls == []
