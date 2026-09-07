"""Native, bounded BigQuery vector reads and replay-safe batch loads."""

import hashlib
import json
import math
import re
import uuid
from dataclasses import dataclass
from typing import Any

from google.api_core.exceptions import Conflict
from google.cloud import bigquery

from clearcut.adapters.bigquery import lore_store as lore


@dataclass
class Document:
    page_content: str
    metadata: dict[str, Any]


class BigQueryVectors:
    def __init__(
        self,
        client: Any,
        table: str,
        *,
        location: str = "us-central1",
        timeout: float = 30,
        maximum_bytes_billed: int = 1_000_000_000,
        extra_columns: tuple[str, ...] = (),
    ) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9-]+\.[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+", table):
            raise ValueError("BigQuery table must be a plain project.dataset.table identifier")
        self.client, self.table = client, table
        self.location, self.timeout = location, timeout
        self.maximum_bytes_billed = maximum_bytes_billed
        if any(not re.fullmatch(r"[a-z_]+", name) for name in extra_columns):
            raise ValueError("invalid metadata column")
        self.columns = (*lore.METADATA_COLUMNS, *extra_columns)

    def _query(self, sql: str, parameters: list[Any]) -> list[dict[str, Any]]:
        config = bigquery.QueryJobConfig(
            query_parameters=parameters, maximum_bytes_billed=self.maximum_bytes_billed
        )
        job = self.client.query(
            sql,
            job_config=config,
            location=self.location,
            job_id="clearcut_read_" + uuid.uuid4().hex,
            retry=None,
            job_retry=None,
            timeout=self.timeout,
        )
        return [dict(row) for row in job.result(timeout=self.timeout, retry=None, job_retry=None)]

    def _scope(self, filters: dict[str, Any] | None) -> tuple[str, list[Any]]:
        if (
            not filters
            or not isinstance(filters.get("project_id"), str)
            or not filters["project_id"].strip()
        ):
            raise ValueError("project scope is required for every vector read")
        if set(filters) - set(self.columns):
            raise ValueError("unsupported vector filter")
        clauses, parameters = [], []
        for index, (key, value) in enumerate(sorted(filters.items())):
            if not isinstance(value, str):
                raise ValueError("vector filters must contain strings")
            parameter = f"scope_{index}"
            clauses.append(f"`{key}` = @{parameter}")
            parameters.append(bigquery.ScalarQueryParameter(parameter, "STRING", value))
        return " AND ".join(clauses), parameters

    def _document(self, row: dict[str, Any]) -> Document:
        return Document(str(row["content"]), {key: row.get(key) for key in self.columns})

    def similarity_search_by_vector_with_score(
        self,
        embedding: list[float],
        filter: dict[str, str] | None = None,
        k: int = 5,
    ) -> list[tuple[lore._Document, float]]:
        if not 1 <= k <= 100 or not embedding or not all(math.isfinite(v) for v in embedding):
            raise ValueError("invalid vector or result limit")
        where, parameters = self._scope(filter)
        parameters.extend(
            [
                bigquery.ArrayQueryParameter("vector", "FLOAT64", embedding),
                bigquery.ScalarQueryParameter("limit", "INT64", k),
            ]
        )
        # Deduplicate logical documents before ranking. Filtering precedes
        # distance/limit so another project's rows cannot affect the result set.
        sql = f"""WITH scoped AS (
          SELECT * EXCEPT(row_number) FROM (
            SELECT *, ROW_NUMBER() OVER(PARTITION BY doc_id ORDER BY content_hash) row_number
            FROM `{self.table}` WHERE {where}) WHERE row_number = 1)
          SELECT *, ML.DISTANCE(embedding, @vector, 'COSINE') AS distance
          FROM scoped ORDER BY distance, doc_id LIMIT @limit"""
        return [
            (self._document(row), float(row["distance"])) for row in self._query(sql, parameters)
        ]

    def get_documents(
        self, ids: list[str] | None = None, filter: dict[str, Any] | None = None
    ) -> list[lore._Document]:
        where, parameters = self._scope(filter)
        if ids is not None:
            where += " AND doc_id IN UNNEST(@ids)"
            parameters.append(bigquery.ArrayQueryParameter("ids", "STRING", ids))
        sql = f"""SELECT * EXCEPT(row_number) FROM (
          SELECT *, ROW_NUMBER() OVER(PARTITION BY doc_id ORDER BY content_hash) row_number
          FROM `{self.table}` WHERE {where}) WHERE row_number = 1 ORDER BY fact_id, doc_id"""
        return [self._document(row) for row in self._query(sql, parameters)]

    def add_texts_with_embeddings(
        self,
        texts: list[str],
        embs: list[list[float]],
        metadatas: list[dict[str, str | int]] | None = None,
    ) -> list[str]:
        if metadatas is None or len(texts) != len(embs) or len(texts) != len(metadatas):
            raise ValueError("texts, vectors and metadata must have matching lengths")
        identifiers, rows = [], []
        for text, embedding, metadata in zip(texts, embs, metadatas):
            if not metadata.get("project_id") or set(metadata) - set(self.columns):
                raise ValueError("scoped, supported metadata is required")
            if not embedding or not all(math.isfinite(value) for value in embedding):
                raise ValueError("a finite embedding is required")
            identity = json.dumps([text, metadata], sort_keys=True, ensure_ascii=False).encode()
            identifier = hashlib.sha256(identity).hexdigest()
            identifiers.append(identifier)
            rows.append({"doc_id": identifier, "content": text, "embedding": embedding, **metadata})
        if not rows:
            return []
        # Keep each load below the JSON upload budget without truncating records.
        batch: list[dict[str, Any]] = []
        size = 0
        sized = [
            (row, len(json.dumps(row, ensure_ascii=False).encode()))
            for row in sorted(rows, key=lambda value: value["doc_id"])
        ]
        if any(row_size > 4_000_000 for _, row_size in sized):
            raise ValueError("single lore record exceeds the supported load size")
        for row, row_size in sized:
            if batch and size + row_size > 4_000_000:
                self._load(batch)
                batch, size = [], 0
            batch.append(row)
            size += row_size
        if batch:
            self._load(batch)
        return identifiers

    def _load(self, rows: list[dict[str, Any]]) -> None:
        payload = json.dumps(rows, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
        job_id = "clearcut_lore_" + hashlib.sha256(self.table.encode() + payload).hexdigest()
        config = bigquery.LoadJobConfig(
            write_disposition="WRITE_APPEND", create_disposition="CREATE_NEVER"
        )
        try:
            job = self.client.load_table_from_json(
                rows,
                self.table,
                job_id=job_id,
                location=self.location,
                job_config=config,
                timeout=self.timeout,
                num_retries=0,
            )
        except Conflict:
            job = self.client.get_job(
                job_id, location=self.location, timeout=self.timeout, retry=None
            )
        job.result(timeout=self.timeout, retry=None)
