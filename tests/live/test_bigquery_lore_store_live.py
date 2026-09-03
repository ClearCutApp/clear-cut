"""`BigQueryLoreStore` against the `clearcut.lore_vectors` table.

The proof is `fact_id`. The adapter rebuilds it from the `content_hash`
metadata column BigQuery stored and returned (`lore_store.py:129-138`), so a
digest matching `content_hash(text)` means the row made a full round trip
through the service rather than being handed back by a fake.

Writes are not immediately visible for read, so the search polls rather than
asserting once. A bare sequential assert here fails intermittently and teaches
everyone to rerun the suite until it passes, which is worse than no test.
"""

import time

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


@pytest.mark.live
@requires("GOOGLE_CLOUD_PROJECT")
def test_an_indexed_fact_comes_back_carrying_the_hash_bigquery_stored() -> None:
    project = env("GOOGLE_CLOUD_PROJECT")
    embeddings = VertexAIEmbeddings(
        project=project, location="us-central1", model="text-embedding-005"
    )
    store = BigQueryLoreStore(
        vector_store=BigQueryVectorStore(
            embedding=embeddings,
            project_id=project,
            dataset_name="clearcut",
            table_name="lore_vectors",
            location="us-central1",
        ),
        embeddings=embeddings,
    )
    project_id = scratch_id("live-lore")
    fact = BibleFact(fact_id="seed", kind=FactKind.LORE, text=_TEXT, source="episode 1 p.4")

    store.index(project_id, [fact])

    deadline = time.monotonic() + _POLL_SECONDS
    found: list[BibleFact] = []
    while time.monotonic() < deadline:
        found = store.search(project_id, "How did Mara's brother die?", 3)
        if found:
            break
        time.sleep(_POLL_INTERVAL)

    assert found, f"nothing came back for {project_id} within {_POLL_SECONDS}s"
    assert found[0].text == _TEXT
    assert found[0].fact_id == content_hash(_TEXT), (
        "fact_id is rebuilt from the content_hash metadata column; a mismatch "
        "means BigQuery did not store and return it"
    )


@pytest.mark.live
@requires("GOOGLE_CLOUD_PROJECT")
def test_a_project_with_nothing_indexed_returns_no_facts() -> None:
    """The `project_id` metadata filter holds.

    Cross-project leakage is this adapter's one fatal failure mode: a producer
    reading another production's bible facts. An unfiltered search would return
    every row the previous test wrote.
    """
    project = env("GOOGLE_CLOUD_PROJECT")
    embeddings = VertexAIEmbeddings(
        project=project, location="us-central1", model="text-embedding-005"
    )
    store = BigQueryLoreStore(
        vector_store=BigQueryVectorStore(
            embedding=embeddings,
            project_id=project,
            dataset_name="clearcut",
            table_name="lore_vectors",
            location="us-central1",
        ),
        embeddings=embeddings,
    )

    assert store.search(scratch_id("live-empty"), "anything at all", 3) == []
