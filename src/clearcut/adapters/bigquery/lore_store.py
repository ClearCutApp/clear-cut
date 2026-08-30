"""BigQuery-backed LoreStore: indexes and retrieves project-scoped bible facts.

Wraps `BigQueryVectorStore` and an embeddings client from
`langchain-google-community` / `langchain-google-vertexai` (ADR 0004,
docs/plan/sdd.md Section 3). `BigQueryVectorStore` does not chunk: one row
per `Scene` and one row per `BibleFact` is this module's own design.
Metadata columns are `project_id`, `kind` (`bible_fact` or `scene`),
`episode`, `scene_number`, `page`, and `content_hash` -- always a `str` or an
`int`, never a `float`, because float equality is not what the store's
dict-filter WHERE clause performs.

Constructor parameters are typed against narrow local `Protocol`s rather than
the concrete pydantic-validated SDK classes: constructing a real
`BigQueryVectorStore` already performs a `get_table` network call inside its
own model validator, which a hand-written unit-test fake must not need to
satisfy (AGENT.md Section 5). A real `BigQueryVectorStore` and a real
embeddings client (`VertexAIEmbeddings`, text-embedding-005) already satisfy
these `Protocol`s structurally, so `composition.py` wires this adapter with
the real instances unchanged. The same reasoning applies to the returned
`Document`-shaped rows: a local `_Document` `Protocol` (`page_content`,
`metadata`) stands in for `langchain_core.documents.Document`, which
satisfies it structurally without this module importing it.
"""

from collections.abc import Sequence
from typing import Any, Protocol

from clearcut.domain.bible import BibleFact, FactKind
from clearcut.domain.script import Scene, content_hash

_KIND_BIBLE_FACT = "bible_fact"
_KIND_SCENE = "scene"


class LoreUnavailable(Exception):
    """The BigQuery vector store or the embedding call failed."""


class _Embedder(Protocol):
    """The subset of `Embeddings` this adapter calls."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class _Document(Protocol):
    """The subset of `langchain_core.documents.Document` this adapter reads."""

    page_content: str
    metadata: dict[str, Any]


class _VectorStore(Protocol):
    """The subset of `BigQueryVectorStore` this adapter calls."""

    def add_texts_with_embeddings(
        self,
        texts: list[str],
        embs: list[list[float]],
        metadatas: list[dict[str, str | int]] | None = None,
    ) -> list[str]: ...

    def similarity_search_by_vector_with_score(
        self,
        embedding: list[float],
        filter: dict[str, str] | None = None,
        k: int = 5,
    ) -> Sequence[tuple[_Document, float]]: ...


class BigQueryLoreStore:
    """Indexes and retrieves project-scoped bible facts and scenes."""

    def __init__(self, vector_store: _VectorStore, embeddings: _Embedder) -> None:
        self._vector_store = vector_store
        self._embeddings = embeddings

    def index(self, project_id: str, records: list[BibleFact | Scene]) -> None:
        texts = [record.text for record in records]
        metadatas = [_metadata_for(project_id, record) for record in records]
        try:
            embeddings = self._embeddings.embed_documents(texts)
            self._vector_store.add_texts_with_embeddings(
                texts=texts, embs=embeddings, metadatas=metadatas
            )
        except Exception as exc:
            raise LoreUnavailable(f"failed to index {len(records)} record(s): {exc}") from exc

    def search(self, project_id: str, query: str, limit: int) -> list[BibleFact]:
        if not project_id.strip():
            raise ValueError("project_id must not be blank")
        try:
            embedding = self._embeddings.embed_query(query)
            results = self._vector_store.similarity_search_by_vector_with_score(
                embedding, filter={"project_id": project_id}, k=limit
            )
        except Exception as exc:
            raise LoreUnavailable(f"lore search failed for project {project_id!r}: {exc}") from exc
        facts = [
            _bible_fact_from(document)
            for document, _score in results
            if document.metadata.get("kind") == _KIND_BIBLE_FACT
        ]
        return facts[:limit]


def _metadata_for(project_id: str, record: BibleFact | Scene) -> dict[str, str | int]:
    if isinstance(record, Scene):
        return {
            "project_id": project_id,
            "kind": _KIND_SCENE,
            "episode": "",
            "scene_number": record.number,
            "page": record.page_start,
            "content_hash": record.content_hash,
        }
    return {
        "project_id": project_id,
        "kind": _KIND_BIBLE_FACT,
        "episode": "",
        "scene_number": 0,
        "page": 0,
        "content_hash": content_hash(record.text),
    }


def _bible_fact_from(document: _Document) -> BibleFact:
    metadata = document.metadata
    episode = metadata.get("episode") or "-"
    page = metadata.get("page", 0)
    return BibleFact(
        fact_id=str(metadata.get("content_hash", "")),
        kind=FactKind.LORE,
        text=document.page_content,
        source=f"episode {episode} p.{page}",
    )
