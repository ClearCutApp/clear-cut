"""BigQuery-backed LoreStore: indexes and retrieves project-scoped bible facts.

Wraps `BigQueryVectorStore` and an embeddings client from
`langchain-google-community` / `langchain-google-vertexai` (ADR 0004,
docs/plan/sdd.md Section 3). `BigQueryVectorStore` does not chunk: one row
per `Scene` and one row per `BibleFact` is this module's own design.
Metadata columns are `project_id`, `kind` (`bible_fact` or `scene`),
`episode`, `scene_number`, `page`, `content_hash`, `fact_id`, `fact_kind` and
`source` -- always a `str` or an `int`, never a `float`, because float
equality is not what the store's dict-filter WHERE clause performs. Both
record types write all nine, because one BigQuery table holds both and a row
that omits a column is a row the table cannot store.

The last three exist so a `BibleFact` comes back as the fact that went in.
Without them `fact_id` was rebuilt from the content hash on every read, so a
fact indexed as `FACT-001` answered to a hex digest afterwards, its kind was
always reported `LORE` whatever it was written as, and `contradicts` on a
continuity finding pointed at an id no caller could look up.

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
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.script import Scene, content_hash

_KIND_BIBLE_FACT = "bible_fact"
_KIND_SCENE = "scene"

# Every metadata column a row carries, facts and scenes alike. Named here
# because `BigQueryVectorStore` fixes the table's schema on first write and
# refuses a later insert that carries a column the table does not have, so
# `infra/provision_lore_schema.py` has to widen a table provisioned before
# ADR 0014 -- and it reads this list rather than repeating it.
METADATA_COLUMNS = (
    "project_id",
    "kind",
    "episode",
    "scene_number",
    "page",
    "content_hash",
    "fact_id",
    "fact_kind",
    "source",
)

# The three ADR 0014 added, all `STRING`. A table created before them has the
# other six and nothing else.
IDENTITY_COLUMNS = ("fact_id", "fact_kind", "source")


class LoreUnavailable(SourceUnavailable):
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

    def get_documents(
        self, ids: list[str] | None = None, filter: dict[str, Any] | None = None
    ) -> Sequence[_Document]: ...


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

    def facts(self, project_id: str) -> list[BibleFact]:
        """Every bible fact recorded for one project, in stored order.

        `GET /api/projects/{project_id}/bible` lists the whole bible, which
        is a read with no query to embed -- `search` would need one, and
        would then rank and truncate a list the producer expects whole.
        """
        if not project_id.strip():
            raise ValueError("project_id must not be blank")
        try:
            documents = self._vector_store.get_documents(
                filter={"project_id": project_id, "kind": _KIND_BIBLE_FACT}
            )
        except Exception as exc:
            raise LoreUnavailable(f"lore read failed for project {project_id!r}: {exc}") from exc
        return [
            _bible_fact_from(document)
            for document in documents
            if document.metadata.get("kind") == _KIND_BIBLE_FACT
        ]


def _metadata_for(project_id: str, record: BibleFact | Scene) -> dict[str, str | int]:
    if isinstance(record, Scene):
        return {
            "project_id": project_id,
            "kind": _KIND_SCENE,
            "episode": "",
            "scene_number": record.number,
            "page": record.page_start,
            "content_hash": record.content_hash,
            "fact_id": "",
            "fact_kind": "",
            "source": "",
        }
    return {
        "project_id": project_id,
        "kind": _KIND_BIBLE_FACT,
        "episode": "",
        "scene_number": 0,
        "page": 0,
        "content_hash": content_hash(record.text),
        "fact_id": record.fact_id,
        "fact_kind": record.kind.value,
        "source": record.source,
    }


def _bible_fact_from(document: _Document) -> BibleFact:
    """The stored fact, by its own identity where the row carries one.

    Rows written before `fact_id`, `fact_kind` and `source` were stored carry
    six metadata keys rather than nine, and BigQuery hands back the column's
    zero value for the three that are missing. The corpus is append-only --
    `LoreStore` offers no way to take a row back -- so those rows are still
    there, and dropping the fallback would turn every one of them into a
    `BibleFact` that raises on a blank `source`. The reconstruction below is
    exactly what this function did before, which is what those rows were
    read as when they were written.
    """
    metadata = document.metadata
    fact_id = str(metadata.get("fact_id") or metadata.get("content_hash", ""))
    stored_kind = str(metadata.get("fact_kind") or "")
    episode = metadata.get("episode") or "-"
    page = metadata.get("page", 0)
    source = str(metadata.get("source") or f"episode {episode} p.{page}")
    return BibleFact(
        fact_id=fact_id,
        kind=FactKind(stored_kind) if stored_kind else FactKind.LORE,
        text=document.page_content,
        source=source,
    )
