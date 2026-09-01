"""Vertex AI Search grounding adapter (ADR 0005, SDD Section 3).

Grounds a query in one jurisdiction's legal corpus by calling Gemini's
`generate_content` with the Vertex AI Search retrieval tool, filtered to
that jurisdiction's `corpus_prefix` (docs/plan/infrastructure.md Section 5:
"Per-request jurisdiction filtering goes through the retrieval tool's
`filter` field"). Vertex AI Search itself runs on the Discovery Engine API,
and a grounded response carries `groundingMetadata.groundingChunks`, which
this adapter reads as citations. A response with no chunks is discarded
rather than trusted (docs/plan/agentic-workflow.md Sections 4 and 8).
"""

import time
from typing import Protocol

from google.genai import types
from opentelemetry import metrics, trace

from clearcut.application.ports import GroundedAnswer
from clearcut.domain.errors import EnrichmentMissing
from clearcut.domain.finding import Citation
from clearcut.domain.jurisdiction import Jurisdiction


def _record_stage(stage: str, start: float) -> None:
    """CP-031 (ADR 0008, SDD Section 6); see `adapters/gcp/document_ai.py`
    for why the tracer/meter lookups happen fresh on every call."""
    duration_ms = (time.perf_counter() - start) * 1000
    metrics.get_meter(__name__).create_histogram(
        "clearcut_stage_latency_ms", unit="ms", description="Pipeline stage latency"
    ).record(duration_ms, {"stage": stage})


# gemini-3.1-flash-lite backs retrieval-grounded answers (SDD Section 3,
# ADR 0002); gemini-3.7-flash is reserved for extraction. Not a constructor
# argument: it has never varied, so it is not config (AGENT.md Section 4).
_MODEL = "gemini-3.1-flash-lite"


class NoGroundedSource(EnrichmentMissing):
    """Raised when a response carries no citation-bearing grounding chunk."""

    def __init__(self, query: str) -> None:
        super().__init__(f"no grounded source for query: {query!r}")
        self.query = query


class _VertexSearchClient(Protocol):
    """The one call this adapter needs from `google.genai.Client.models`."""

    def generate_content(
        self,
        *,
        model: str,
        contents: str,
        config: types.GenerateContentConfig,
    ) -> types.GenerateContentResponse: ...


class VertexSearchGrounding:
    """Implements `LegalGrounding` over one Vertex AI Search data store."""

    def __init__(self, client: _VertexSearchClient, data_store_id: str) -> None:
        self._client = client
        self._data_store_id = data_store_id

    def ground(self, query: str, jurisdiction: Jurisdiction) -> GroundedAnswer:
        stage_start = time.perf_counter()
        with trace.get_tracer(__name__).start_as_current_span("ground"):
            answer = self._ground(query, jurisdiction)
        _record_stage("ground", stage_start)
        return answer

    def _ground(self, query: str, jurisdiction: Jurisdiction) -> GroundedAnswer:
        prefix = jurisdiction.corpus_prefix.strip().rstrip("/")
        if not prefix:
            raise ValueError(f"blank corpus_prefix for jurisdiction {jurisdiction.code!r}")

        response = self._client.generate_content(
            model=_MODEL,
            contents=query,
            config=self._grounded_config(prefix),
        )

        chunks = self._grounding_chunks(response)
        if not chunks:
            raise NoGroundedSource(query)
        return GroundedAnswer(text=response.text or "", citations=self._citations(chunks))

    def _grounded_config(self, prefix: str) -> types.GenerateContentConfig:
        search = types.VertexAISearch(
            datastore=self._data_store_id,
            filter=f'jurisdiction: ANY("{prefix}")',
        )
        tool = types.Tool(retrieval=types.Retrieval(vertex_ai_search=search))
        return types.GenerateContentConfig(tools=[tool])

    @staticmethod
    def _grounding_chunks(
        response: types.GenerateContentResponse,
    ) -> tuple[types.GroundingChunk, ...]:
        candidates = response.candidates or ()
        if not candidates:
            return ()
        metadata = candidates[0].grounding_metadata
        if metadata is None or not metadata.grounding_chunks:
            return ()
        return tuple(metadata.grounding_chunks)

    @staticmethod
    def _citations(chunks: tuple[types.GroundingChunk, ...]) -> tuple[Citation, ...]:
        citations: list[Citation] = []
        for chunk in chunks:
            context = chunk.retrieved_context
            if context is None:
                continue
            citations.append(
                Citation(
                    uri=context.uri or "",
                    title=context.title or "",
                    snippet=context.text or "",
                )
            )
        return tuple(citations)
