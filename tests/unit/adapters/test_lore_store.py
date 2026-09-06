"""Unit tests for the BigQuery-backed LoreStore adapter (CP-008).

The real `BigQueryVectorStore` and embeddings client both call out to Google
Cloud at construction and query time, so these tests fake the vector-store
boundary directly (AGENT.md Section 5): `FakeVectorStore` and `FakeEmbedder`
are hand-written stand-ins for the two narrow methods this adapter actually
calls, with real enough behaviour (storing rows, filtering by metadata) to
make the project-isolation and limit criteria non-vacuous.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from clearcut.adapters.bigquery.lore_store import BigQueryLoreStore, LoreUnavailable
from clearcut.application.ports import LoreStore
from clearcut.domain.bible import BibleFact, FactKind
from clearcut.domain.script import Scene


@dataclass
class _Row:
    """Stands in for `langchain_core.documents.Document` (`page_content`,
    `metadata`) without importing it -- see `lore_store.py`'s module
    docstring for why."""

    page_content: str
    metadata: dict[str, Any]


class FakeEmbedder:
    """Records calls; returns a one-dimensional embedding per text."""

    def __init__(self) -> None:
        self.embed_documents_calls: list[list[str]] = []
        self.embed_query_calls: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.embed_documents_calls.append(texts)
        return [[float(len(text))] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.embed_query_calls.append(text)
        return [float(len(text))]


class FakeVectorStore:
    """Stores rows in memory; filters on exact metadata equality like the
    real store's dict-filter WHERE clause (AGENT.md Section 5: real enough
    behaviour to exercise, not a canned response)."""

    def __init__(self) -> None:
        self.add_calls: list[dict[str, Any]] = []
        self._rows: list[tuple[str, dict[str, Any]]] = []

    def add_texts_with_embeddings(
        self,
        texts: list[str],
        embs: list[list[float]],
        metadatas: list[dict[str, str | int]] | None = None,
    ) -> list[str]:
        self.add_calls.append({"texts": texts, "embs": embs, "metadatas": metadatas})
        rows_metadata = metadatas or [{} for _ in texts]
        for text, metadata in zip(texts, rows_metadata):
            self._rows.append((text, metadata))
        return [str(i) for i in range(len(texts))]

    def similarity_search_by_vector_with_score(
        self,
        embedding: list[float],
        filter: dict[str, str] | None = None,
        k: int = 5,
    ) -> list[tuple[_Row, float]]:
        return [(row, 0.0) for row in self._matching(filter)][:k]

    def get_documents(
        self, ids: list[str] | None = None, filter: dict[str, Any] | None = None
    ) -> list[_Row]:
        return self._matching(filter)

    def _matching(self, filter: dict[str, Any] | None) -> list[_Row]:
        filter = filter or {}
        return [
            _Row(page_content=text, metadata=metadata)
            for text, metadata in self._rows
            if all(metadata.get(key) == value for key, value in filter.items())
        ]

    def add_row(self, text: str, metadata: dict[str, Any]) -> None:
        """Plant a row directly, without going through `index`.

        The fallback path needs a row shaped the way the corpus held them
        before the identity columns existed, and `index` can no longer write
        one.
        """
        self._rows.append((text, metadata))


class ExplodingVectorStore:
    """Raises on every call, standing in for a real langchain/BigQuery error."""

    def add_texts_with_embeddings(
        self,
        texts: list[str],
        embs: list[list[float]],
        metadatas: list[dict[str, str | int]] | None = None,
    ) -> list[str]:
        raise RuntimeError("simulated BigQuery load failure")

    def similarity_search_by_vector_with_score(
        self,
        embedding: list[float],
        filter: dict[str, str] | None = None,
        k: int = 5,
    ) -> list[tuple[_Row, float]]:
        raise RuntimeError("simulated BigQuery query failure")

    def get_documents(
        self, ids: list[str] | None = None, filter: dict[str, Any] | None = None
    ) -> list[_Row]:
        raise RuntimeError("simulated BigQuery read failure")


def _bible_fact(fact_id: str = "fact-1", text: str = "The dog is named Rex.") -> BibleFact:
    return BibleFact(fact_id=fact_id, kind=FactKind.LORE, text=text, source="Bible p. 3")


def _scene(number: int = 1) -> Scene:
    return Scene(
        number=number,
        heading="INT. HOUSE - DAY",
        page_start=2,
        page_end=2,
        text="Rex barks at the mail carrier.",
    )


def test_adapter_satisfies_the_lorestore_port() -> None:
    adapter = BigQueryLoreStore(vector_store=FakeVectorStore(), embeddings=FakeEmbedder())
    checked: LoreStore = adapter
    assert isinstance(checked, LoreStore)


_METADATA_KEYS = {
    "project_id",
    "kind",
    "episode",
    "scene_number",
    "page",
    "content_hash",
    "fact_id",
    "fact_kind",
    "source",
}


def test_the_declared_column_list_is_the_one_a_row_actually_writes() -> None:
    """`infra/provision_lore_schema.py` widens the BigQuery table from
    `METADATA_COLUMNS`. A name there that no row writes provisions a column
    nothing fills; a name missing from it is a column the table will not have,
    and BigQuery rejects the insert outright."""
    from clearcut.adapters.bigquery.lore_store import IDENTITY_COLUMNS, METADATA_COLUMNS

    assert set(METADATA_COLUMNS) == _METADATA_KEYS
    assert set(IDENTITY_COLUMNS) <= set(METADATA_COLUMNS)


def test_indexing_a_bible_fact_writes_exactly_the_nine_metadata_keys() -> None:
    vector_store = FakeVectorStore()
    adapter = BigQueryLoreStore(vector_store=vector_store, embeddings=FakeEmbedder())

    adapter.index("proj-a", [_bible_fact()])

    metadata = vector_store.add_calls[0]["metadatas"][0]
    assert set(metadata.keys()) == _METADATA_KEYS
    assert metadata["kind"] == "bible_fact"


def test_indexing_a_scene_writes_the_same_metadata_keys_a_fact_does() -> None:
    """One BigQuery table holds both, so both write the same columns. A row
    that omits three of them is a row the table cannot store."""
    vector_store = FakeVectorStore()
    adapter = BigQueryLoreStore(vector_store=vector_store, embeddings=FakeEmbedder())

    adapter.index("proj-a", [_scene()])

    assert set(vector_store.add_calls[0]["metadatas"][0].keys()) == _METADATA_KEYS


def test_indexing_a_bible_fact_writes_its_own_identity() -> None:
    """`FACT-001` was indexed and a hex digest came back, because `fact_id`,
    the kind and the source were never stored and had to be rebuilt on read.
    They are stored now."""
    vector_store = FakeVectorStore()
    adapter = BigQueryLoreStore(vector_store=vector_store, embeddings=FakeEmbedder())

    adapter.index("proj-a", [BibleFact("FACT-001", FactKind.POLICY, "No smoking.", "policy.pdf")])

    metadata = vector_store.add_calls[0]["metadatas"][0]
    assert metadata["fact_id"] == "FACT-001"
    assert metadata["fact_kind"] == "POLICY"
    assert metadata["source"] == "policy.pdf"


def test_bible_fact_metadata_values_are_str_or_int_never_float() -> None:
    vector_store = FakeVectorStore()
    adapter = BigQueryLoreStore(vector_store=vector_store, embeddings=FakeEmbedder())

    adapter.index("proj-a", [_bible_fact()])

    metadata = vector_store.add_calls[0]["metadatas"][0]
    for value in metadata.values():
        assert isinstance(value, (str, int))
        assert not isinstance(value, float)


def test_indexing_a_scene_writes_kind_scene_with_scene_number_and_content_hash() -> None:
    vector_store = FakeVectorStore()
    adapter = BigQueryLoreStore(vector_store=vector_store, embeddings=FakeEmbedder())
    scene = _scene(number=7)

    adapter.index("proj-a", [scene])

    metadata = vector_store.add_calls[0]["metadatas"][0]
    assert metadata["kind"] == "scene"
    assert metadata["scene_number"] == 7
    assert metadata["content_hash"] == scene.content_hash


def test_search_filters_to_the_requested_project() -> None:
    vector_store = FakeVectorStore()
    adapter = BigQueryLoreStore(vector_store=vector_store, embeddings=FakeEmbedder())
    adapter.index("proj-a", [_bible_fact(fact_id="a-1", text="Fact belonging to project A.")])
    adapter.index("proj-b", [_bible_fact(fact_id="b-1", text="Fact belonging to project B.")])

    results = adapter.search("proj-a", "project A fact", limit=10)

    assert len(results) == 1
    assert results[0].text == "Fact belonging to project A."
    assert all("project B" not in fact.text for fact in results)


def test_search_returns_at_most_limit_results() -> None:
    vector_store = FakeVectorStore()
    adapter = BigQueryLoreStore(vector_store=vector_store, embeddings=FakeEmbedder())
    facts: list[BibleFact | Scene] = [
        _bible_fact(fact_id=f"a-{i}", text=f"Fact number {i}.") for i in range(3)
    ]
    adapter.index("proj-a", facts)

    results = adapter.search("proj-a", "fact", limit=2)

    assert len(results) == 2


def test_search_excludes_scene_rows_sharing_a_project_with_bible_facts() -> None:
    vector_store = FakeVectorStore()
    adapter = BigQueryLoreStore(vector_store=vector_store, embeddings=FakeEmbedder())
    adapter.index("proj-a", [_bible_fact(text="The dog is named Rex."), _scene()])

    results = adapter.search("proj-a", "Rex", limit=10)

    assert len(results) == 1
    assert results[0].text == "The dog is named Rex."


def test_search_with_blank_project_id_raises_before_touching_store() -> None:
    vector_store = FakeVectorStore()
    embedder = FakeEmbedder()
    adapter = BigQueryLoreStore(vector_store=vector_store, embeddings=embedder)

    with pytest.raises(ValueError):
        adapter.search("   ", "a query", limit=5)

    assert vector_store.add_calls == []
    assert embedder.embed_query_calls == []


def test_search_wraps_a_store_error_as_lore_unavailable() -> None:
    adapter = BigQueryLoreStore(vector_store=ExplodingVectorStore(), embeddings=FakeEmbedder())

    with pytest.raises(LoreUnavailable):
        adapter.search("proj-a", "a query", limit=5)


def test_index_wraps_a_store_error_as_lore_unavailable() -> None:
    adapter = BigQueryLoreStore(vector_store=ExplodingVectorStore(), embeddings=FakeEmbedder())

    with pytest.raises(LoreUnavailable):
        adapter.index("proj-a", [_bible_fact()])


def test_a_fact_survives_index_and_search_with_the_identity_it_went_in_with() -> None:
    vector_store = FakeVectorStore()
    adapter = BigQueryLoreStore(vector_store=vector_store, embeddings=FakeEmbedder())
    fact = BibleFact("FACT-007", FactKind.POLICY, "No brand names in dialogue.", "policy.pdf p.2")

    adapter.index("proj-a", [fact])

    assert adapter.search("proj-a", "brands", limit=5) == [fact]


def test_facts_returns_every_fact_of_the_project() -> None:
    vector_store = FakeVectorStore()
    adapter = BigQueryLoreStore(vector_store=vector_store, embeddings=FakeEmbedder())
    lore = BibleFact("FACT-001", FactKind.LORE, "Mariana never left the province.", "bible p.4")
    policy = BibleFact("FACT-002", FactKind.POLICY, "No smoking on camera.", "policy.pdf")
    adapter.index("proj-a", [lore, policy])

    assert adapter.facts("proj-a") == [lore, policy]


def test_facts_excludes_scenes_indexed_into_the_same_project() -> None:
    vector_store = FakeVectorStore()
    adapter = BigQueryLoreStore(vector_store=vector_store, embeddings=FakeEmbedder())
    adapter.index("proj-a", [_bible_fact(), _scene()])

    results = adapter.facts("proj-a")

    assert [fact.fact_id for fact in results] == ["fact-1"]


def test_facts_excludes_another_projects_facts() -> None:
    vector_store = FakeVectorStore()
    adapter = BigQueryLoreStore(vector_store=vector_store, embeddings=FakeEmbedder())
    adapter.index("proj-a", [_bible_fact(fact_id="a-1", text="Fact belonging to project A.")])
    adapter.index("proj-b", [_bible_fact(fact_id="b-1", text="Fact belonging to project B.")])

    assert [fact.fact_id for fact in adapter.facts("proj-a")] == ["a-1"]


def test_facts_reads_a_row_written_before_the_identity_columns_existed() -> None:
    """Rows already in the corpus carry six metadata keys, not nine. They
    still have to read back as facts, which is what the fallback is for --
    the identity it reconstructs is the content hash the old code used."""
    vector_store = FakeVectorStore()
    adapter = BigQueryLoreStore(vector_store=vector_store, embeddings=FakeEmbedder())
    vector_store.add_row(
        "The dog is named Rex.",
        {
            "project_id": "proj-a",
            "kind": "bible_fact",
            "episode": "",
            "scene_number": 0,
            "page": 0,
            "content_hash": "9f2b1c4e",
        },
    )

    results = adapter.facts("proj-a")

    assert len(results) == 1
    assert results[0].fact_id == "9f2b1c4e"
    assert results[0].kind is FactKind.LORE
    assert results[0].source == "episode - p.0"


def test_facts_with_blank_project_id_raises_before_touching_the_store() -> None:
    vector_store = FakeVectorStore()
    adapter = BigQueryLoreStore(vector_store=vector_store, embeddings=FakeEmbedder())

    with pytest.raises(ValueError):
        adapter.facts("   ")


def test_facts_wraps_a_store_error_as_lore_unavailable() -> None:
    adapter = BigQueryLoreStore(vector_store=ExplodingVectorStore(), embeddings=FakeEmbedder())

    with pytest.raises(LoreUnavailable):
        adapter.facts("proj-a")
