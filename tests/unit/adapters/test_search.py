"""Tests for the Parallel Search API web-grounding adapter (CP-062, ADR 0003).

The transport is faked at the httpx level (`httpx.MockTransport`), the seam
`parallel.Parallel` itself exposes for injecting a client, rather than
patching the SDK (AGENT.md Section 5) -- the same shape
`test_research.py` established for the Task API sibling.

`request.content` is inspected inside the handler because that is the only
place the call shape is provable: `mode`, the `objective`, and the keyword
`search_queries` are request fields, so no assertion on the returned
`GroundedAnswer` can tell a `fast` call from an `advanced` one.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from clearcut.adapters.parallel.search import (
    NoWebEvidence,
    ParallelWebSearch,
    WebSearchUnavailable,
)
from clearcut.application.ports import GroundedAnswer, WebGrounding
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.jurisdiction import jurisdiction_for
from tests.unit.conftest import install_in_memory_telemetry, metric_attributes_by_name

_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "parallel_search_result.json"
_ARGENTINA = jurisdiction_for("AR")
_QUESTION = "Can we show the mural in scene 12 without the artist's permission?"

_OFFICIAL_STATUTE = "https://www.argentina.gob.ar/normativa/nacional/ley-11723-42755/texto"
_OFFICIAL_PDF = "https://www.ign.gob.ar/sites/default/files/Ley_11723.pdf"
_WIKI = "https://commons.wikimedia.org/wiki/Commons:Freedom_of_panorama/Argentina"
_SMUGGLED = "https://evil.example/www.argentina.gob.ar/normativa/ley-11723.pdf"
_EMPTY_EXCERPT = "https://www.lexology.com/library/detail.aspx?g=copyright-argentina"


def _result_body() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text())  # type: ignore[no-any-return]


def _adapter(
    result_body: dict[str, Any],
    *,
    status: int = 200,
    requests: list[dict[str, Any]] | None = None,
) -> ParallelWebSearch:
    def handler(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(json.loads(request.content))
        return httpx.Response(status, json=result_body)

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    return ParallelWebSearch(http_client, "parallel-test-key")


def test_adapter_implements_web_grounding_port() -> None:
    adapter = _adapter(_result_body())
    checked: WebGrounding = adapter
    assert isinstance(checked, WebGrounding)


def test_fixture_search_result_returns_a_grounded_answer_with_mapped_citations() -> None:
    adapter = _adapter(_result_body())

    answer = adapter.search(_QUESTION, _ARGENTINA)

    assert isinstance(answer, GroundedAnswer)
    citation = answer.citations[0]
    assert citation.uri == _OFFICIAL_STATUTE
    assert citation.title == "Ley 11.723 - Regimen Legal de la Propiedad Intelectual"
    assert citation.snippet.startswith("Articulo 2.")
    assert citation.snippet in answer.text


def test_the_answer_text_opens_with_a_provenance_line() -> None:
    """A producer must not read a wiki excerpt as a statute the corpus vouched
    for, so the first line says where the answer came from."""
    adapter = _adapter(_result_body())

    answer = adapter.search(_QUESTION, _ARGENTINA)

    first_line = answer.text.splitlines()[0].lower()
    assert "web search" in first_line


def test_citations_are_capped_at_three() -> None:
    adapter = _adapter(_result_body())

    answer = adapter.search(_QUESTION, _ARGENTINA)

    assert len(answer.citations) == 3


def test_a_result_with_an_empty_first_excerpt_is_dropped() -> None:
    """An empty excerpt is a link, not evidence: nothing can be quoted from it."""
    adapter = _adapter(_result_body())

    answer = adapter.search(_QUESTION, _ARGENTINA)

    assert _EMPTY_EXCERPT not in [citation.uri for citation in answer.citations]


def test_an_official_host_outranks_a_higher_relevance_non_official_one() -> None:
    """The measured behaviour this rank exists for.

    Parallel returns `results` in decreasing relevance and, on the real
    Argentina mural query, ranked Wikimedia Commons above both
    `argentina.gob.ar` pages. A plain top-three cap would hand a producer a
    wiki as citation one for a legal question.
    """
    adapter = _adapter(_result_body())

    answer = adapter.search(_QUESTION, _ARGENTINA)

    uris = [citation.uri for citation in answer.citations]
    assert uris == [_OFFICIAL_STATUTE, _OFFICIAL_PDF, _WIKI]


def test_the_wiki_is_ranked_down_but_never_filtered_out() -> None:
    """A rank, not a gate: `is_official` reads domain authority, which is not
    jurisdictional relevance, so excluding what it rejects would have dropped
    the most directly responsive analysis of the three."""
    adapter = _adapter(_result_body())

    answer = adapter.search(_QUESTION, _ARGENTINA)

    assert _WIKI in [citation.uri for citation in answer.citations]


def test_a_host_suffix_smuggled_into_the_path_is_not_treated_as_official() -> None:
    """`evil.example/www.argentina.gob.ar/...` is not a government host.

    The fixture's own ordering cannot prove this on its own -- the smuggling
    URL is below the cap anyway -- so this body holds only two results, with
    the smuggler ranked first.
    """
    body = copy.deepcopy(_result_body())
    smuggled = next(item for item in body["results"] if item["url"] == _SMUGGLED)
    official = next(item for item in body["results"] if item["url"] == _OFFICIAL_STATUTE)
    body["results"] = [smuggled, official]
    adapter = _adapter(body)

    answer = adapter.search(_QUESTION, _ARGENTINA)

    assert [citation.uri for citation in answer.citations] == [_OFFICIAL_STATUTE, _SMUGGLED]


def test_every_result_dropped_raises_no_web_evidence_carrying_the_question() -> None:
    body = copy.deepcopy(_result_body())
    for item in body["results"]:
        item["excerpts"] = []
    adapter = _adapter(body)

    with pytest.raises(NoWebEvidence) as excinfo:
        adapter.search(_QUESTION, _ARGENTINA)

    assert excinfo.value.question == _QUESTION


def test_a_result_whose_url_is_not_http_is_dropped() -> None:
    """A `data:` or bare-string URL is not a source a producer can open."""
    body = copy.deepcopy(_result_body())
    body["results"] = [
        {
            "url": "data:text/plain;base64,SGVsbG8=",
            "title": "inline",
            "publish_date": None,
            "excerpts": ["Looks like evidence, points nowhere."],
        }
    ]
    adapter = _adapter(body)

    with pytest.raises(NoWebEvidence):
        adapter.search(_QUESTION, _ARGENTINA)


def test_the_request_asks_for_fast_mode() -> None:
    """`advanced` is the API default at roughly 3s, which blows the
    sub-second budget `infrastructure.md` Section 7.1 sets for the on-camera
    lookup. Omitting `mode` therefore silently buys the slow tier."""
    requests: list[dict[str, Any]] = []
    adapter = _adapter(_result_body(), requests=requests)

    adapter.search(_QUESTION, _ARGENTINA)

    assert requests[0]["mode"] == "fast"


def test_the_objective_names_the_jurisdiction_and_carries_the_question() -> None:
    requests: list[dict[str, Any]] = []
    adapter = _adapter(_result_body(), requests=requests)

    adapter.search(_QUESTION, _ARGENTINA)

    objective = requests[0]["objective"]
    assert _ARGENTINA.display_name in objective
    assert _QUESTION in objective


def test_search_queries_are_short_keyword_queries_not_the_question() -> None:
    """The Search API asks for concise keyword queries, 3-6 words each, and
    2-3 of them; the natural-language question belongs in `objective`."""
    requests: list[dict[str, Any]] = []
    adapter = _adapter(_result_body(), requests=requests)

    adapter.search(_QUESTION, _ARGENTINA)

    queries = requests[0]["search_queries"]
    assert 2 <= len(queries) <= 3
    for query in queries:
        assert 3 <= len(query.split()) <= 6, query
        assert query != _QUESTION
    assert all(_ARGENTINA.display_name in query for query in queries)


def test_non_2xx_response_raises_web_search_unavailable_with_status_code() -> None:
    adapter = _adapter(_result_body(), status=503)

    with pytest.raises(WebSearchUnavailable) as excinfo:
        adapter.search(_QUESTION, _ARGENTINA)

    assert excinfo.value.status_code == 503
    assert "503" in str(excinfo.value)


def _adapter_with_transport_failure(error: httpx.TransportError) -> ParallelWebSearch:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    return ParallelWebSearch(http_client, "parallel-test-key")


def test_a_connect_error_raises_web_search_unavailable_with_no_status_code() -> None:
    adapter = _adapter_with_transport_failure(httpx.ConnectError("connection refused"))

    with pytest.raises(WebSearchUnavailable) as excinfo:
        adapter.search(_QUESTION, _ARGENTINA)

    assert excinfo.value.status_code is None
    assert isinstance(excinfo.value, SourceUnavailable)


def test_a_2xx_whose_body_the_sdk_cannot_read_becomes_web_search_unavailable() -> None:
    """A proxy answers 200 with an HTML interstitial (ADR 0011, CP-056).

    Without strict validation the SDK hands back a bare `str` and the
    `AttributeError` on the next line reaches the producer as a 500 -- an
    upstream outage reported as a ClearCut bug.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text="<html>upstream gateway</html>", headers={"content-type": "text/html"}
        )

    adapter = ParallelWebSearch(
        httpx.Client(transport=httpx.MockTransport(handler)), "parallel-test-key"
    )

    with pytest.raises(WebSearchUnavailable) as caught:
        adapter.search(_QUESTION, _ARGENTINA)

    assert isinstance(caught.value, SourceUnavailable)
    assert caught.value.status_code is None
    assert not isinstance(caught.value, NoWebEvidence)


def test_search_opens_a_web_search_span_and_records_stage_latency(isolated_otel: None) -> None:
    span_exporter, metric_reader = install_in_memory_telemetry()
    adapter = _adapter(_result_body())

    adapter.search(_QUESTION, _ARGENTINA)

    spans = [span for span in span_exporter.get_finished_spans() if span.name == "web_search"]
    assert len(spans) == 1

    latency_points = metric_attributes_by_name(metric_reader)["clearcut_stage_latency_ms"]
    assert latency_points
    assert all(point["stage"] == "web_search" for point in latency_points)


def test_search_transport_has_explicit_timeout_and_no_hidden_retry() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(503, json={"message": "unavailable"})

    adapter = ParallelWebSearch(
        httpx.Client(transport=httpx.MockTransport(handler)), "test-key", timeout=9
    )
    with pytest.raises(WebSearchUnavailable):
        adapter.search(_QUESTION, _ARGENTINA)
    assert len(calls) == 1
    assert calls[0].extensions["timeout"]["read"] == 9
