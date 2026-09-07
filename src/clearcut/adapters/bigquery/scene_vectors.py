"""Revision-scoped BigQuery scene evidence, separate from editable bible facts."""

from collections.abc import Callable
from typing import Any

from clearcut.adapters.bigquery import lore_store as lore
from clearcut.application.lore_projection_ports import LoreLease
from clearcut.domain.errors import SourceUnavailable


class BigQuerySceneVectors:
    def __init__(
        self,
        store: Callable[[str], lore._VectorStore],
        embed: Callable[[list[str], str, bool], list[list[float]]],
    ) -> None:
        self.store, self.embed_call = store, embed

    def embed(self, texts: list[str], provider_config_json: str) -> list[list[float]]:
        return self.embed_call(texts, provider_config_json, False)

    def append(
        self, lease: LoreLease, scenes: list[dict[str, Any]], embeddings: list[list[float]]
    ) -> None:
        metadata = [
            {
                "project_id": lease.project_id,
                "organization_id": lease.organization_id,
                "analysis_id": lease.analysis_id,
                "revision_id": lease.revision_id,
                "scene_id": scene["scene_id"],
                "kind": "scene",
                "episode": "",
                "scene_number": scene["number"],
                "page": scene["page_start"],
                "content_hash": scene["content_hash"],
                "fact_id": "",
                "fact_kind": "",
                "source": (
                    f"Revision {lease.revision_id}, scene {scene['number']}, "
                    f"excerpt at character {scene['chunk_start']}"
                ),
            }
            for scene in scenes
        ]
        try:
            self.store(lease.provider_config_json).add_texts_with_embeddings(
                [s["text"] for s in scenes], embeddings, metadata
            )
        except Exception as exc:
            raise SourceUnavailable("scene indexing unavailable") from exc

    def search(self, scope: dict[str, Any], question: str, limit: int) -> list[dict[str, Any]]:
        filters = {
            key: scope[key]
            for key in ("project_id", "organization_id", "analysis_id", "revision_id")
        }
        filters["kind"] = "scene"
        try:
            embedding = self.embed_call([question], scope["provider_config_json"], True)[0]
            rows = self.store(scope["provider_config_json"]).similarity_search_by_vector_with_score(
                embedding, filters, limit
            )
            result = []
            for document, _ in rows:
                if any(document.metadata.get(key) != value for key, value in filters.items()):
                    raise ValueError("scene result scope mismatch")
                result.append({"text": document.page_content, **document.metadata})
            return result
        except Exception as exc:
            raise SourceUnavailable("current revision scene retrieval unavailable") from exc
