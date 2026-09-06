"""Behaviour tests for infra/provision_lore_schema.py.

`BigQueryVectorStore` fixes `clearcut.lore_vectors`'s schema the first time it
writes and refuses every later insert that carries a column the table does not
have. The table was created with six metadata columns, so the first `index`
call after ADR 0014 answered:

    400 Provided Schema does not match Table clearcut-hack:clearcut.lore_vectors.
    Cannot add fields (field: fact_id)

Only the live tier found that; every unit test in this repo passed. This
script widens the table, and these tests hold it to the column list
`lore_store.py` declares.

The script is loaded by path rather than imported, because `infra/` is a
directory of standalone scripts with no `__init__.py`.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from clearcut.adapters.bigquery.lore_store import IDENTITY_COLUMNS

SCRIPT = Path(__file__).resolve().parents[3] / "infra" / "provision_lore_schema.py"

REQUIRED = ("GOOGLE_CLOUD_PROJECT",)


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("provision_lore_schema", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _RecordingJob:
    def result(self) -> None:
        return None


class RecordingBqClient:
    """Records every statement and completes each job, which is the seam
    `add_identity_columns` takes -- so this test needs no BigQuery dataset."""

    def __init__(self) -> None:
        self.statements: list[str] = []
        self.completed = 0

    def query(self, statement: str) -> _RecordingJob:
        self.statements.append(statement)
        self.completed += 1
        return _RecordingJob()


def test_one_alter_per_identity_column() -> None:
    client = RecordingBqClient()

    load_script().add_identity_columns(client, "clearcut-hack")

    assert len(client.statements) == len(IDENTITY_COLUMNS)
    for column in IDENTITY_COLUMNS:
        assert any(f"ADD COLUMN IF NOT EXISTS {column} STRING" in s for s in client.statements), (
            column
        )


def test_every_statement_names_the_lore_vectors_table() -> None:
    client = RecordingBqClient()

    load_script().add_identity_columns(client, "clearcut-hack")

    for statement in client.statements:
        assert "`clearcut-hack`.`clearcut`.`lore_vectors`" in statement, statement


def test_every_statement_is_idempotent() -> None:
    """`ADD COLUMN IF NOT EXISTS` so a second run is a no-op, and so a table
    the vector store created fresh with all nine columns is left alone."""
    client = RecordingBqClient()

    load_script().add_identity_columns(client, "clearcut-hack")

    for statement in client.statements:
        assert "ADD COLUMN IF NOT EXISTS" in statement, statement


def test_nothing_is_dropped_or_rewritten() -> None:
    """Widening is additive: existing rows keep their six columns and read
    back through `_bible_fact_from`'s fallback. A statement that dropped or
    replaced anything would destroy a corpus with no way to rebuild it --
    `LoreStore` has no delete, and nothing else holds these facts."""
    client = RecordingBqClient()

    load_script().add_identity_columns(client, "clearcut-hack")

    joined = " ".join(client.statements).upper()
    for forbidden in ("DROP", "DELETE", "TRUNCATE", "CREATE OR REPLACE"):
        assert forbidden not in joined, forbidden


def test_each_job_is_waited_on_rather_than_only_submitted() -> None:
    """A BigQuery DDL query is a job. Submitting it and exiting leaves the
    column half-added, and the next `index` fails the same way."""
    client = RecordingBqClient()

    load_script().add_identity_columns(client, "clearcut-hack")

    assert client.completed == len(client.statements)


@pytest.mark.parametrize("missing", REQUIRED)
def test_a_missing_credential_exits_naming_that_variable(missing: str) -> None:
    env = {name: "placeholder" for name in REQUIRED}
    del env[missing]
    env["PATH"] = "/usr/bin:/bin"

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode != 0
    assert missing in result.stderr, result.stderr


def test_dry_run_prints_the_statements_without_connecting() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("ADD COLUMN IF NOT EXISTS") == len(IDENTITY_COLUMNS)
    for column in IDENTITY_COLUMNS:
        assert column in result.stdout, column


def test_an_unknown_argument_is_refused() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--recreate"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
        check=False,
    )

    assert result.returncode != 0
    assert "--recreate" in result.stderr
