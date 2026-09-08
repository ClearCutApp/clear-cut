"""Answers a legal question from the live web through the Parallel Search API
(ADR 0003, docs/plan/infrastructure.md Section 7).

The sibling adapter in `research.py` asks the Task API a research question and
waits minutes for a cited answer. This one asks the Search API a question the
producer is holding the camera on, and has under a second to answer it. Same
partner, same key, different surface: `Parallel.search` is one POST to
`/v1/search`, so nothing here waits on a run.

`AnswerProjectQuestion` calls this only when the licensed corpus produced no
citation of its own. That ordering is the whole point -- the corpus is the
stronger source and answers first; this is what the producer gets instead of
silence, marked as the weaker claim it is (`application/ports.py`,
`WebGrounding`).

Turning the excerpts Parallel returns into an answer is quoting, not
generating: every sentence in the text below is either a fixed provenance line
or an excerpt Parallel wrote, attributed to the URL it came from. CHECKPOINTS.md
Decision D12 rules out in-process free-text generation, and translating a
service's own words into a domain type is what every other adapter in this
package does.
"""

from __future__ import annotations

import re
import time
from typing import Literal

import httpx
from opentelemetry import metrics, trace
from parallel import APIConnectionError, APIResponseValidationError, APIStatusError, Parallel
from parallel.types.search_result import SearchResult
from parallel.types.web_search_result import WebSearchResult

from clearcut.application.ports import GroundedAnswer
from clearcut.domain.errors import EnrichmentMissing, SourceUnavailable
from clearcut.domain.finding import Citation
from clearcut.domain.jurisdiction import Jurisdiction
from clearcut.observability import stage_span

# `advanced` is what the API uses when `mode` is omitted, and it answers in
# roughly 3s -- past the sub-second budget the on-camera lookup has
# (docs/plan/infrastructure.md Section 7.1), so leaving this unset silently
# buys the slow tier. `fast` answers inside a second at the cheapest price
# band and still returns the excerpts this adapter quotes; `turbo` is faster
# again but trades away exactly those excerpts. Never varied, so a constant
# rather than constructor config (AGENT.md Section 4). Annotated with the
# SDK's own `Literal`, so a typo here fails `mypy` rather than a live call.
_MODE: Literal["turbo", "fast", "basic", "advanced"] = "fast"

# Three citations is what the answer panel shows a producer without turning a
# question into a reading list. Never varied, same reason as `_MODE`.
_MAX_CITATIONS = 3

# The host suffixes this adapter ranks first. Duplicated from
# `infra/fetch_legal_corpus.py` rather than shared: that file is an operator
# CLI outside `src/`, which `src/` may not import (AGENT.md Section 2), and
# two copies is the second use, not the third -- AGENT.md Section 4 says
# duplicate twice and extract on the third.
_OFFICIAL_SUFFIXES = (
    ".gob.ar",
    ".gov",
    ".gob.mx",
    ".gob.es",
    ".gouv.fr",
    ".gov.uk",
    ".gov.in",
    ".gov.br",
    ".go.kr",
    ".gc.ca",
    "wipo.int",
    "oas.org",
)

# The first line of every answer. A producer reading an excerpt has no way to
# tell a statute from a blog once it is inside a paragraph, and this adapter
# quotes both, so the answer says where it came from before it says anything
# else.
_PROVENANCE = (
    "From a live web search, not ClearCut's licensed legal corpus. "
    "Check each source before relying on it."
)

# Words carrying no search signal. Dropped so `_queries` can build the 3-6
# word keyword queries the Search API asks for out of what the producer
# actually named.
_STOP_WORDS = frozenset(
    (
        "and any are but can did does for from has have her his how its "
        "may must need not our out that the their them there they this "
        "was were what when where which who why will with without would "
        "you your"
    ).split()
)

# Long enough to carry meaning: drops "we", "in", "it", and the stranded "s"
# an apostrophe leaves behind ("artist's" -> "artist", "s").
_MIN_KEYWORD_LENGTH = 3

# The SDK asks for 2-3 queries of 3-6 words each (`_client.py:378`), so this
# takes at most three keywords and pads each query with a fixed tail.
_MAX_KEYWORDS = 3

# What `_queries` falls back to when a question is nothing but stop words, so
# the request is never a bare jurisdiction name.
_FALLBACK_KEYWORDS = ("film", "clearance")

# Letters only: a scene number or a year is not a search term, and an
# apostrophe would put "artist's" in a keyword query as its own token.
_WORD = re.compile(r"[a-z]+")


def _record_stage(stage: str, start: float) -> None:
    """CP-031 (ADR 0008, SDD Section 6); see `adapters/gcp/document_ai.py`
    for why the tracer/meter lookups happen fresh on every call."""
    duration_ms = (time.perf_counter() - start) * 1000
    metrics.get_meter(__name__).create_histogram(
        "clearcut_stage_latency_ms", unit="ms", description="Pipeline stage latency"
    ).record(duration_ms, {"stage": stage})


class NoWebEvidence(EnrichmentMissing):
    """Raised when no search result survives the quality gate in `_answer`."""

    def __init__(self, question: str) -> None:
        super().__init__("no usable web evidence found")
        self.question = question


class WebSearchUnavailable(SourceUnavailable):
    """Raised when the Parallel Search API could not be reached, timed out, or
    responded with a non-2xx status."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ParallelWebSearch:
    """Implements `WebGrounding` over the Parallel Search API."""

    def __init__(self, http_client: httpx.Client, api_key: str, *, timeout: float = 45) -> None:
        # max_retries=0 and _strict_response_validation=True for the reasons
        # `research.py` records: a retry hides a transport failure behind
        # backoff sleeps this budget cannot afford, and lenient validation
        # hands back a bare `str` when a proxy answers 200 with an HTML
        # interstitial, reporting an upstream outage as a ClearCut 500
        # (ADR 0011, CP-056).
        self._timeout = timeout
        self._client = Parallel(
            api_key=api_key,
            http_client=http_client,
            max_retries=0,
            _strict_response_validation=True,
        )

    def search(self, question: str, jurisdiction: Jurisdiction) -> GroundedAnswer:
        stage_start = time.perf_counter()
        with stage_span(trace.get_tracer(__name__), "web_search"):
            answer = self._search(question, jurisdiction)
        _record_stage("web_search", stage_start)
        return answer

    def _search(self, question: str, jurisdiction: Jurisdiction) -> GroundedAnswer:
        try:
            result = self._client.search(
                search_queries=_queries(question, jurisdiction),
                objective=_objective(question, jurisdiction),
                mode=_MODE,
                timeout=self._timeout,
            )
        # First because it is a sibling of the other two, not a subclass:
        # `APIResponseValidationError` extends `APIError` directly, so ordering
        # it after `APIStatusError` would read as narrowing when it is not.
        except APIResponseValidationError as error:
            raise WebSearchUnavailable(
                "Parallel Search API returned an invalid response"
            ) from error
        except APIStatusError as error:
            raise WebSearchUnavailable(
                f"Parallel Search API responded with status {error.status_code}",
                status_code=error.status_code,
            ) from error
        except APIConnectionError as error:
            raise WebSearchUnavailable("Parallel Search API request failed") from error

        return _answer(result, question)


def _objective(question: str, jurisdiction: Jurisdiction) -> str:
    """The natural-language half of the request.

    The producer's whole sentence goes here and nowhere else: the SDK asks
    for `search_queries` to be concise keyword queries, so passing the
    question as one would spend the search on a sentence the index does not
    contain.
    """
    return (
        f"Answer this film-clearance question under the law of "
        f"{jurisdiction.display_name}: {question}"
    )


def _keywords(question: str) -> list[str]:
    """The question's own search terms, in the order it named them."""
    found = [
        word
        for word in _WORD.findall(question.lower())
        if word not in _STOP_WORDS and len(word) >= _MIN_KEYWORD_LENGTH
    ]
    return found[:_MAX_KEYWORDS] if found else list(_FALLBACK_KEYWORDS)


def _queries(question: str, jurisdiction: Jurisdiction) -> list[str]:
    """Three keyword queries, each naming the jurisdiction (SDK `_client.py:378`).

    Every one carries the territory because the same question has a different
    answer in each: `mural public street copyright` retrieves the freedom-of-
    panorama countries, which Argentina is not one of. Beyond that the three
    widen outwards -- the producer's own terms, then the clearance framing,
    then the statute a citation should ideally land on -- because the API
    ranks across all of them together rather than answering each in turn.
    """
    place = jurisdiction.display_name
    keywords = _keywords(question)
    return [
        f"{place} {' '.join(keywords)} law",
        f"{place} {keywords[0]} rights clearance",
        f"{place} copyright law statute",
    ]


def _host(url: str) -> str:
    """The host of `url`, lowercased, or "" when it names none."""
    return url.split("://", 1)[-1].split("/", 1)[0].split("?", 1)[0].lower()


def _is_official(url: str) -> bool:
    """Whether `url` sits on a government or intergovernmental host.

    Read from the host, not the whole URL, so
    `evil.example/www.argentina.gob.ar/ley.pdf` cannot smuggle a suffix past
    it -- the same check, and the same reason, as
    `infra/fetch_legal_corpus.py`.
    """
    host = _host(url)
    return any(host == suffix.lstrip(".") or host.endswith(suffix) for suffix in _OFFICIAL_SUFFIXES)


def _is_evidence(result: WebSearchResult) -> bool:
    """Whether a result is something a producer could actually open and read.

    A URL with no scheme is not a source, and a result whose first excerpt is
    empty is a link rather than evidence: there is nothing to quote from it,
    so it would arrive as a bare citation under a paragraph it did not
    support.
    """
    if not result.url.startswith(("http://", "https://")):
        return False
    return bool(result.excerpts) and bool(result.excerpts[0].strip())


def _answer(result: SearchResult, question: str) -> GroundedAnswer:
    """The quality gate: drop what is not evidence, rank official hosts up, cap.

    A rank, never a filter. `_is_official` measures domain authority, which is
    not jurisdictional relevance -- it accepts a US `.gov` page describing
    Argentine law and rejects a SADAIC or INPI page that is squarely on point.
    As a gate that weakness silently removes correct sources; as a sort key it
    only reorders. Measured against the live API on 2026-09-06, Parallel's own
    relevance put Wikimedia Commons above both `argentina.gob.ar` pages, and
    that Wikimedia page carried the most directly responsive analysis of the
    three -- so a plain top-three cap would have led with a wiki, and a filter
    would have thrown the best paragraph away. `sorted` is stable, so within
    each group Parallel's relevance order survives untouched.
    """
    usable = [item for item in result.results if _is_evidence(item)]
    ranked = sorted(usable, key=lambda item: not _is_official(item.url))[:_MAX_CITATIONS]
    if not ranked:
        raise NoWebEvidence(question)

    citations = tuple(
        Citation(uri=item.url, title=item.title or "", snippet=item.excerpts[0].strip())
        for item in ranked
    )
    return GroundedAnswer(text=_text(citations), citations=citations)


def _text(citations: tuple[Citation, ...]) -> str:
    """The provenance line, then each excerpt attributed to where it came from."""
    quoted = "\n\n".join(
        f"{citation.snippet} (source: {citation.title or citation.uri})" for citation in citations
    )
    return f"{_PROVENANCE}\n\n{quoted}"
