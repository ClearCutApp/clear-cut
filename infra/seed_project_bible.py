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

Additive only, and idempotent. `LoreStore` offers no way to remove a row,
which SDD section 4.3 already records as a known gap -- so a second run that
wrote again would leave two copies of the fact in the corpus permanently, with
no way to undo it. `seed` reads the project's facts first and writes nothing
when the fact is already there.

`clearcut.lore_vectors` must carry the identity columns before this runs:
`infra/provision_lore_schema.py` adds them, and without them BigQuery rejects
the write outright.

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
    from clearcut.domain.script import content_hash
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


def seed(store: Any) -> bool:
    """Index the scenario's bible fact, unless it is already there.

    Returns whether anything was written.

    Idempotent because every other provisioning script in `infra/` is, and
    because `LoreStore` offers no way to take a row back: without this, a
    second run leaves two copies of the fact in the corpus permanently, and
    duplicates crowd the continuity check's top-k retrieval.

    **Matched on the hash of the text, not on `fact_id`.** The corpus holds
    rows of two shapes. A row written since ADR 0014 carries its own
    `fact_id`, so it reads back as `FACT-001`. A row written before that
    carries none, so `_bible_fact_from` rebuilds `fact_id` from the stored
    content hash and it answers to a hex digest instead. Hashing the text of
    whatever came back recognises the fact under either identity, and a guard
    comparing `fact_id` would miss one of the two and re-index on every run
    while looking correct.

    Reads `facts` rather than `search`: listing the bible is exact, where a
    similarity search returns the k nearest and could push an already-seeded
    fact past the cutoff once the project holds enough others.

    Takes the store rather than building one, which is the seam that lets a
    test assert what was indexed without a BigQuery dataset.
    """
    fact = scenario.BIBLE_FACT
    wanted = content_hash(fact.text)
    existing = store.facts(scenario.PROJECT_ID)
    if any(content_hash(found.text) == wanted for found in existing):
        return False
    store.index(scenario.PROJECT_ID, [fact])
    return True


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

    if seed(store):
        print("indexed:")
    else:
        print("already present, nothing written:")
    print(_describe())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
