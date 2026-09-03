"""`VertexSearchGrounding` against the legal-corpus data store.

Two assertions, and the second is the one that matters. Answer text proves
nothing -- a model answers a legal question whether or not retrieval ran. Only a
genuinely grounded response carries `groundingMetadata.groundingChunks`, so a
citation URI pointing into `gs://clearcut-legal-corpus/` is the proof the data
store was actually queried.

The zero-result test is the only automated check that the console-only
"mark `jurisdiction` Indexable" step was done. Skip that step and filtered
queries silently match every jurisdiction, so a Mexico script gets grounded
against US statutes with no error anywhere (ADR 0005).
"""

import pytest
from google import genai

from clearcut.adapters.gcp.vertex_search import VertexSearchGrounding
from clearcut.domain.errors import EnrichmentMissing
from clearcut.domain.jurisdiction import jurisdiction_for
from tests.live.conftest import env, requires

# Spanish, because the Argentine corpus is Spanish. Probed against the real
# data store on 2026-09-03: the equivalent English question retrieves zero
# documents unfiltered, while this one retrieves Ley 11.723 both filtered and
# unfiltered. Retrieval does not cross the language boundary, and nothing in
# SDD section 4.1 step 5 makes `AnalyzeScript` ask in the corpus language --
# recorded as a finding rather than papered over here.
_QUERY = "¿La ley exige licencia para usar una obra musical protegida en una película?"


def _adapter() -> tuple[VertexSearchGrounding, genai.Client]:
    """Returns the client alongside the adapter, and callers must keep it.

    `VertexSearchGrounding` holds `client.models`, not the client. Letting the
    client fall out of scope closes its transport, and the next call fails with
    "Cannot send a request, as the client has been closed" -- which looks like
    an outage and is really a lifetime bug in the test. `composition.py` keeps
    the client alive for the life of the app, so this is a test-only hazard.
    """
    client = genai.Client(
        vertexai=True,
        project=env("GOOGLE_CLOUD_PROJECT"),
        location="global",  # Gemini 3 is global-only; see composition._GENAI_LOCATION
    )
    adapter = VertexSearchGrounding(
        client=client.models,
        data_store_id=env("VERTEX_SEARCH_DATA_STORE_ID"),
    )
    return adapter, client


@pytest.mark.live
@requires("GOOGLE_CLOUD_PROJECT", "VERTEX_SEARCH_DATA_STORE_ID")
def test_grounded_answer_carries_a_citation_from_the_corpus_bucket() -> None:
    adapter, _client = _adapter()

    answer = adapter.ground(_QUERY, jurisdiction_for("AR"))

    assert answer.citations, (
        "no citations: the response was not retrieval-grounded, so the data "
        "store was never consulted"
    )
    uris = [citation.uri for citation in answer.citations]
    assert any(uri.startswith("gs://clearcut-legal-corpus/argentina/") for uri in uris), (
        f"citations came from outside the Argentine corpus prefix: {uris}"
    )


@pytest.mark.live
@requires("GOOGLE_CLOUD_PROJECT", "VERTEX_SEARCH_DATA_STORE_ID")
def test_a_jurisdiction_with_no_documents_grounds_nothing() -> None:
    """The `jurisdiction` field is Indexable, proved the only way it can be.

    South Korea has no prefix in the corpus. If the filter works, retrieval
    returns zero chunks and the adapter raises `NoGroundedSource`. If the field
    was never marked Indexable, the filter is ignored, Argentine statutes come
    back instead, and this test fails with an answer it should never have got.
    """
    adapter, _client = _adapter()

    with pytest.raises(EnrichmentMissing):
        adapter.ground(_QUERY, jurisdiction_for("KR"))
