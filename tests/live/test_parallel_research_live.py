"""`ParallelRightsResearch` against the Parallel Task API.

This is the partner-track test. ADR 0003 enters the Parallel track and
`docs/plan/proposal.md:45` commits to the Task API with per-claim citations, so
an unproven Parallel call is the one gap the submission cannot absorb.

The proof is `citations`. `_first_cited_claim` (`research.py:144-164`) returns
only a claim whose `basis` carries citations and raises `NoRightsHolderFound`
otherwise, so a real `https://` URI is evidence Parallel researched the asset
rather than that a fake returned a fixture.

Slowest test in the tier by a wide margin: `task_run.result` blocks until the
run completes and the `core` processor takes minutes. The explicit 600s client
timeout matches what the SDK falls back to anyway -- stated here so the budget
is visible rather than inherited by accident.
"""

import httpx
import pytest

from clearcut.adapters.parallel.research import ParallelRightsResearch
from clearcut.application.ports import Confidence
from clearcut.domain.finding import Category
from clearcut.domain.jurisdiction import jurisdiction_for
from tests.live.conftest import env, requires

_TIMEOUT = httpx.Timeout(600.0, connect=5.0)


@pytest.mark.live
@requires("PARALLEL_API_KEY")
def test_researches_a_real_rights_holder_and_returns_cited_claims() -> None:
    with httpx.Client(timeout=_TIMEOUT) as http_client:
        research = ParallelRightsResearch(http_client=http_client, api_key=env("PARALLEL_API_KEY"))

        claim = research.find("Hotel California", Category.COPYRIGHT_WORKS, jurisdiction_for("ES"))

    assert claim.holder.strip(), "a claim with no holder is not an answer"
    assert claim.confidence in Confidence
    assert claim.citations, (
        "no citations: the adapter raises NoRightsHolderFound when every claim "
        "is uncited, so reaching here without them means the basis was empty"
    )
    # Scheme, not host: Parallel searches the live web, so which sources come
    # back varies run to run and some are plain http. Asserting on shape keeps
    # this test about "these are real web citations" rather than about whichever
    # sources today's search happened to rank.
    assert all(citation.uri.startswith(("https://", "http://")) for citation in claim.citations), [
        citation.uri for citation in claim.citations
    ]
