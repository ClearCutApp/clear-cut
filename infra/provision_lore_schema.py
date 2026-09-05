#!/usr/bin/env python3
"""Widen `clearcut.lore_vectors` with the three identity columns (ADR 0014).

`BigQueryVectorStore` fixes the table's schema the first time it writes, then
refuses every later insert that carries a column the table does not have. The
table was created with six metadata columns, so the first `index` call after
`fact_id`, `fact_kind` and `source` were added answered:

    400 Provided Schema does not match Table clearcut-hack:clearcut.lore_vectors.
    Cannot add fields (field: fact_id)

which means no bible fact can be written at all until the table is widened.
Nothing in the unit tier could see that; `tests/live/test_bigquery_lore_store_live.py`
is what found it.

Additive and idempotent. `ADD COLUMN IF NOT EXISTS` leaves a table that
already has the column alone, so a second run is a no-op and a table the
vector store created fresh with all nine columns is untouched. Existing rows
keep their six and read back through `_bible_fact_from`'s fallback, which is
the reason that fallback exists.

Usage:
    .venv/bin/python infra/provision_lore_schema.py [--dry-run]

It reads the column list from `lore_store.py` rather than repeating it, so it
needs the project's dependencies -- a bare `python3` will not do.

--dry-run prints the exact statements a real run would issue and connects to
nothing, so it needs no credentials.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

try:
    from clearcut.adapters.bigquery.lore_store import IDENTITY_COLUMNS  # noqa: E402
except ModuleNotFoundError as exc:  # pragma: no cover - depends on the interpreter
    print(
        f"provision_lore_schema.py: {exc.name} is not importable.\n"
        "Run it with the project interpreter:\n"
        "    .venv/bin/python infra/provision_lore_schema.py --dry-run",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

REQUIRED = ("GOOGLE_CLOUD_PROJECT",)

# The same values `composition.py` and `infra/seed_project_bible.py` fix for
# the single region and dataset. Repeated rather than imported because
# importing `composition` would build the whole adapter graph to read two
# constants.
_LOCATION = "us-central1"
_DATASET = "clearcut"
_TABLE = "lore_vectors"


def alter_statements(gcp_project: str) -> list[str]:
    """One `ALTER TABLE` per identity column, read from `lore_store.py`.

    Every column is `STRING`: `fact_id` is `FACT-NNN`, `fact_kind` is a
    `FactKind` name, and `source` is free text a producer typed.
    """
    table = f"`{gcp_project}`.`{_DATASET}`.`{_TABLE}`"
    return [
        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} STRING"
        for column in IDENTITY_COLUMNS
    ]


def add_identity_columns(client: Any, gcp_project: str) -> None:
    """Issue each statement and wait for it.

    A BigQuery DDL query is a job. Submitting it and exiting leaves the column
    half-added and the next `index` fails the same way, so each job is waited
    on rather than only started.
    """
    for statement in alter_statements(gcp_project):
        client.query(statement).result()


class _PrintingJob:
    def result(self) -> None:
        return None


class _PrintingClient:
    """Prints each statement instead of executing it.

    Dry-run drives the same `add_identity_columns` the real run drives, so
    what it shows cannot fall out of step with what it would do.
    """

    def query(self, statement: str) -> _PrintingJob:
        print(statement)
        return _PrintingJob()


def _missing_credentials() -> list[str]:
    return [name for name in REQUIRED if not os.environ.get(name, "").strip()]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    dry_run = "--dry-run" in args
    unknown = [arg for arg in args if arg != "--dry-run"]
    if unknown:
        print(f"unexpected argument: {unknown[0]}", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        return 2

    if dry_run:
        add_identity_columns(_PrintingClient(), "your-gcp-project")
        return 0

    missing = _missing_credentials()
    if missing:
        print(
            f"provision_lore_schema.py: missing required environment {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    from google.cloud import bigquery

    gcp_project = os.environ["GOOGLE_CLOUD_PROJECT"]
    add_identity_columns(bigquery.Client(project=gcp_project, location=_LOCATION), gcp_project)
    print(f"widened {_DATASET}.{_TABLE} with {', '.join(IDENTITY_COLUMNS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
