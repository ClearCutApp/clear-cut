#!/usr/bin/env python3
"""Seed the demo project's bible fact into the BigQuery lore store.

SDD section 8(d) asserts a CONTINUITY finding, and a contradiction needs
something to contradict. The fact has to be in the LoreStore before the live
end-to-end run, and ADR 0011 rules that seeding as infrastructure rather than
as `POST /api/projects/{id}/bible`: the endpoint is a route plus a use case
plus tests, this reaches the same state in an hour, and the SDD keeps reporting
the endpoint as MISSING.

The fact is not restated here. It comes from `adapters/demo/scenario.py`, the
one place it is defined, so what this seeds and what mock mode serves cannot
disagree about which fact scene 3 contradicts.

Additive only. `LoreStore` exposes `index` and `search` and nothing that
removes a row, which SDD section 4.3 already records as a known gap. Running
this twice indexes the fact twice; BigQuery holds both rows and a search
returns the same text either way.

Usage:
    .venv/bin/python infra/seed_project_bible.py [--dry-run]

--dry-run prints what a real run would index and connects to nothing, so it
needs no credentials. It also runs under a bare `python3`, because
`lore_store.py` and `scenario.py` reach no further than the stdlib-only domain
layer. A real run imports langchain and needs the project interpreter.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

try:
    from clearcut.adapters.bigquery.lore_store import BigQueryLoreStore
    from clearcut.adapters.demo import scenario
except ModuleNotFoundError as exc:  # pragma: no cover - depends on the interpreter
    print(
        f"seed_project_bible.py: {exc.name} is not importable.\n"
        "Run it with the project interpreter:\n"
        "    .venv/bin/python infra/seed_project_bible.py --dry-run",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

REQUIRED = ("GOOGLE_CLOUD_PROJECT",)

# The same four values `composition.py` fixes for the single region and
# dataset. Repeated rather than imported because importing `composition`
# would build the whole adapter graph to read four constants.
_LOCATION = "us-central1"
_DATASET = "clearcut"
_TABLE = "lore_vectors"
_EMBEDDING_MODEL = "text-embedding-005"


def seed(store: Any) -> None:
    """Index the scenario's bible fact against the scenario's project.

    Takes the store rather than building one, which is the seam that lets a
    test assert what was indexed without a BigQuery dataset.
    """
    store.index(scenario.PROJECT_ID, [scenario.BIBLE_FACT])


def _missing_credentials() -> list[str]:
    return [name for name in REQUIRED if not os.environ.get(name, "").strip()]


def _describe() -> str:
    fact = scenario.BIBLE_FACT
    return (
        f"project: {scenario.PROJECT_ID}\n"
        f"  {fact.fact_id} ({fact.kind}) from {fact.source}\n"
        f"    {fact.text}"
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    dry_run = "--dry-run" in args
    unknown = [arg for arg in args if arg != "--dry-run"]
    if unknown:
        print(f"unexpected argument: {unknown[0]}", file=sys.stderr)
        return 2

    if dry_run:
        print(f"would index into BigQuery table {_DATASET}.{_TABLE} ({_LOCATION}):")
        print(_describe())
        return 0

    missing = _missing_credentials()
    if missing:
        print(
            f"seed_project_bible.py: missing required environment {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    from langchain_google_community import BigQueryVectorStore  # type: ignore[import-untyped]
    from langchain_google_vertexai import VertexAIEmbeddings

    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    embeddings = VertexAIEmbeddings(project=project, location=_LOCATION, model=_EMBEDDING_MODEL)
    store = BigQueryLoreStore(
        vector_store=BigQueryVectorStore(
            embedding=embeddings,
            project_id=project,
            dataset_name=_DATASET,
            table_name=_TABLE,
            location=_LOCATION,
        ),
        embeddings=embeddings,
    )

    seed(store)
    print("indexed:")
    print(_describe())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
