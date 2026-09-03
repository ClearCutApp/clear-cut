"""Tests for the Vertex AI Search grounding adapter (CP-009, ADR 0005)."""

import json
from pathlib import Path

import pytest
from google.genai import errors as genai_errors
from google.genai import types

from clearcut.adapters.gcp.vertex_search import (
    GroundingUnavailable,
    NoGroundedSource,
    VertexSearchGrounding,
)
from clearcut.application.ports import GroundedAnswer, LegalGrounding
from clearcut.domain.errors import EnrichmentMissing, SourceUnavailable
from clearcut.domain.jurisdiction import Jurisdiction, jurisdiction_for
from tests.unit.conftest import install_in_memory_telemetry, metric_attributes_by_name

_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "vertex_grounded_answer.json"
# `locations/global`, because that is where `infra/provision_retrieval_plane.sh`
# creates the store. This constant said `locations/us` until 2026-09-03; the
# fake accepts either, so nothing failed, and the value only had to be right on
# the first real call. `test_identifier_agreement.py` now holds it to what the
# script prints.
_DATA_STORE_ID = (
    "projects/clearcut-hack/locations/global/collections/default_collection/"
    "dataStores/clearcut-legal-corpus"
)


class FakeVertexSearchClient:
    """Hand-written fake standing in for `google.genai.Client.models`."""

    def __init__(
        self,
        response: types.GenerateContentResponse | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self._response = response
        self._error = error
        self.calls: list[dict[str, object]] = []

    def generate_content(
        self,
        *,
        model: str,
        contents: str,
        config: types.GenerateContentConfig,
    ) -> types.GenerateContentResponse:
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self._error is not None:
            raise self._error
        assert self._response is not None
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


# ---------------------------------------------------------------------------
# CP-031 (ADR 0008, SDD Section 6): `ground` opens a "ground" span and
# records `clearcut_stage_latency_ms` with stage="ground" (CP-031 review,
# BLOCKING 2).
# ---------------------------------------------------------------------------


def test_ground_opens_a_ground_span_and_records_stage_latency(isolated_otel: None) -> None:
    span_exporter, metric_reader = install_in_memory_telemetry()
    fake = FakeVertexSearchClient(_load_fixture_response())
    adapter = VertexSearchGrounding(fake, _DATA_STORE_ID)

    adapter.ground("Can I use a Ferrari logo?", jurisdiction_for("AR"))

    spans = [span for span in span_exporter.get_finished_spans() if span.name == "ground"]
    assert len(spans) == 1

    latency_points = metric_attributes_by_name(metric_reader)["clearcut_stage_latency_ms"]
    assert latency_points
    assert all(point["stage"] == "ground" for point in latency_points)


# --- CP-056: an outage is not a missing citation --------------------------
#
# `_ground` called the SDK bare, so a Vertex 503 or a bad data-store ACL
# reached `routes.py`'s generic handler as a 500 reading "internal error".
# `NoGroundedSource` is EnrichmentMissing and degrades the finding; an outage
# is SourceUnavailable and must reach the producer as a 502.


def test_an_api_error_becomes_grounding_unavailable_not_no_grounded_source() -> None:
    adapter = VertexSearchGrounding(
        client=FakeVertexSearchClient(error=genai_errors.ServerError(503, {"error": "down"})),
        data_store_id=_DATA_STORE_ID,
    )

    with pytest.raises(SourceUnavailable) as caught:
        adapter.ground("does this need a licence?", jurisdiction_for("AR"))

    assert isinstance(caught.value, GroundingUnavailable)
    assert not isinstance(caught.value, EnrichmentMissing)


def test_a_client_error_also_becomes_grounding_unavailable() -> None:
    """A 403 on the data store is the likeliest real failure: the service
    account exists but was never granted Discovery Engine access."""
    adapter = VertexSearchGrounding(
        client=FakeVertexSearchClient(error=genai_errors.ClientError(403, {"error": "denied"})),
        data_store_id=_DATA_STORE_ID,
    )

    with pytest.raises(GroundingUnavailable):
        adapter.ground("does this need a licence?", jurisdiction_for("AR"))
