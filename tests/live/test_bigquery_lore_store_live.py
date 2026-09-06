"""`BigQueryLoreStore` against the `clearcut.lore_vectors` table.

The proof is the identity. `fact_id`, `fact_kind` and `source` are metadata
columns BigQuery stored and handed back, so a fact that answers to the id,
the kind and the source it was written with is a fact that made a full round
trip through the service. Before ADR 0014 none of the three was stored and
the adapter rebuilt `fact_id` from the content hash, which is why the fact
indexed as `FACT-001` answered to a digest.

Writes are not immediately visible for read, so the reads poll rather than
asserting once. A bare sequential assert here fails intermittently and teaches
everyone to rerun the suite until it passes, which is worse than no test.
"""

import time
from collections.abc import Callable

import pytest
from langchain_google_community import BigQueryVectorStore  # type: ignore[import-untyped]
from langchain_google_vertexai import VertexAIEmbeddings

from clearcut.adapters.bigquery.lore_store import BigQueryLoreStore
from clearcut.domain.bible import BibleFact, FactKind
from clearcut.domain.script import content_hash
from tests.live.conftest import env, requires, scratch_id

_TEXT = "Mara's brother died in the 1998 fire at the Rosario grain silo."
_POLL_SECONDS = 60
_POLL_INTERVAL = 5


def _store() -> BigQueryLoreStore:
    project = env("GOOGLE_CLOUD_PROJECT")
    embeddings = VertexAIEmbeddings(
        project=project, location="us-central1", model="text-embedding-005"
    )
    return BigQueryLoreStore(
        vector_store=BigQueryVectorStore(
            embedding=embeddings,
            project_id=project,
            dataset_name="clearcut",
            table_name="lore_vectors",
            location="us-central1",
        ),
        embeddings=embeddings,
    )


def _poll(read: Callable[[], list[BibleFact]], project_id: str) -> list[BibleFact]:
    deadline = time.monotonic() + _POLL_SECONDS
    found: list[BibleFact] = []
    while time.monotonic() < deadline:
        found = read()
        if found:
            break
        time.sleep(_POLL_INTERVAL)
    assert found, f"nothing came back for {project_id} within {_POLL_SECONDS}s"
    return found


@pytest.mark.live
@requires("GOOGLE_CLOUD_PROJECT")
def test_an_indexed_fact_comes_back_as_the_fact_that_went_in() -> None:
    store = _store()
    project_id = scratch_id("live-lore")
    fact = BibleFact(fact_id="FACT-001", kind=FactKind.POLICY, text=_TEXT, source="bible.pdf p.4")

    store.index(project_id, [fact])

    found = _poll(lambda: store.search(project_id, "How did Mara's brother die?", 3), project_id)
    assert found[0] == fact, (
        "fact_id, fact_kind and source are metadata columns; a mismatch means "
        "BigQuery did not store and return them"
    )
    # The content hash is still written alongside the identity, and it is
    # still what `infra/seed_project_bible.py` matches a re-run on.
    assert content_hash(found[0].text) == content_hash(_TEXT)


@pytest.mark.live
@requires("GOOGLE_CLOUD_PROJECT")
def test_facts_lists_the_whole_bible_of_one_project() -> None:
    """`search` ranks and truncates; a producer reading their bible expects
    every fact. Two facts written together have to come back as two."""
    store = _store()
    project_id = scratch_id("live-bible")
    lore = BibleFact("FACT-001", FactKind.LORE, _TEXT, "bible.pdf p.4")
    policy = BibleFact("FACT-002", FactKind.POLICY, "No smoking on camera.", "policy.pdf p.1")

    store.index(project_id, [lore, policy])

    found = _poll(lambda: store.facts(project_id), project_id)
    assert sorted(found, key=lambda f: f.fact_id) == [lore, policy]


@pytest.mark.live
@requires("GOOGLE_CLOUD_PROJECT")
def test_a_project_with_nothing_indexed_returns_no_facts() -> None:
    """The `project_id` metadata filter holds.

    Cross-project leakage is this adapter's one fatal failure mode: a producer
    reading another production's bible facts. An unfiltered read would return
    every row the tests above wrote.
    """
    store = _store()
    empty_project = scratch_id("live-empty")

    assert store.search(empty_project, "anything at all", 3) == []
    assert store.facts(empty_project) == []
