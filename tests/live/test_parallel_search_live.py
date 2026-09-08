"""`ParallelWebSearch` against the Parallel Search API.

The second half of the partner-track proof. `test_parallel_research_live.py`
proves the Task API call; this proves the Search API one, which is what makes
`docs/plan/infrastructure.md` Section 11's runtime-proof row true for both
Parallel surfaces rather than one.

The question is deliberately one the licensed corpus misses. `docs/plan/sdd.md`
Section 9.2 records that Vertex AI Search retrieval matches terms rather than
meaning and that six of the eight clearance categories ground against nothing,
so freedom of panorama in Argentina is exactly the shape of question that used
to come back with bible facts and silence.

The proof is the citations. `_answer` (`search.py`) raises `NoWebEvidence`
when nothing survives its gate, so reaching an assertion at all means Parallel
returned excerpts with real URLs behind them -- and the text assertion pins
that the answer quotes those excerpts rather than paraphrasing them, which
`AGENT.md` Section 5 asks for over "no exception was raised".

Fast next to its Task API sibling: `fast` mode answers inside a second, where
`task_run.result` blocks for minutes.
"""

from urllib.parse import urlsplit

import httpx
import pytest

from clearcut.adapters.parallel.search import ParallelWebSearch
from clearcut.domain.jurisdiction import jurisdiction_for
from tests.live.conftest import env, requires

_TIMEOUT = httpx.Timeout(60.0, connect=5.0)
_QUESTION = (
    "Can a production show a copyrighted mural on a public street without the artist's permission?"
)


@pytest.mark.live
@requires("PARALLEL_API_KEY")
def test_answers_a_corpus_miss_from_the_live_web_with_real_citations() -> None:
    with httpx.Client(timeout=_TIMEOUT) as http_client:
        web = ParallelWebSearch(http_client=http_client, api_key=env("PARALLEL_API_KEY"))

        answer = web.search(_QUESTION, jurisdiction_for("AR"))

    assert answer.citations, (
        "no citations: the adapter raises NoWebEvidence when nothing survives "
        "its gate, so reaching here without them means the gate let through an "
        "empty result"
    )
    assert any(citation.uri.startswith("https://") for citation in answer.citations), [
        citation.uri for citation in answer.citations
    ]
    # Hosts, not one host: which sources Parallel ranks varies run to run, so
    # this asserts that they are real ones rather than that today's search
    # happened to return a particular page. `example.*` is the reserved
    # documentation domain a fixture or a fake would reach for.
    hosts = [urlsplit(citation.uri).hostname or "" for citation in answer.citations]
    assert all(host and not host.startswith("example.") for host in hosts), hosts

    snippets = [citation.snippet for citation in answer.citations]
    assert all(snippet.strip() for snippet in snippets), snippets
    # The text quotes the excerpts rather than summarizing them (Decision D12),
    # so every citation's snippet has to be findable in it verbatim.
    assert all(snippet in answer.text for snippet in snippets)
