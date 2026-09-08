"""Behaviour tests for infra/provision_tracker_schema.py.

`ClickHouseTrackerStore.ensure_schema()` had no caller anywhere outside the
adapter's own unit test: not `composition.py`, not `main.py`, not any infra
script. So `tracker_items` and `script_versions` were never created, and the
first live tracker write would have failed on a missing table.

It belongs in `infra/` rather than in `create_app()`. Creating a table is
provisioning, and `tests/unit/test_composition.py` asserts construction opens
no socket -- a DDL call at startup would break that invariant to solve a
problem provisioning already owns.

The script is loaded by path rather than imported, because `infra/` is a
directory of standalone scripts with no `__init__.py`.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "infra" / "provision_tracker_schema.py"

REQUIRED = ("CLICKHOUSE_HOST", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD")


def schema_module() -> ModuleType:
    """The adapter package's DDL, imported the ordinary way.

    The script is loaded by path because `infra/` has no `__init__.py`; the
    schema it reuses is an installed module, and reading `ALTERATIONS` from it
    is what keeps this test asserting about the one copy of the DDL rather
    than about a second list written here.
    """
    from clearcut.adapters.clickhouse import schema

    return schema


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("provision_tracker_schema", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ALL_TABLES = ("tracker_items", "script_versions", "projects", "findings", "analysis_jobs")


class RecordingChClient:
    """Records every DDL statement, returns nothing. The seam `create_tables`
    takes, so this test needs no ClickHouse service."""

    def __init__(self) -> None:
        self.commands: list[str] = []

    def command(self, statement: str) -> None:
        self.commands.append(statement)

    def insert(self, table: str, rows: list[Any], column_names: list[str]) -> None:
        raise AssertionError("provisioning must not write rows")

    def query(self, query: str, parameters: dict[str, Any] | None = None) -> Any:
        raise AssertionError("provisioning must not read rows")


def test_creates_every_table_the_adapters_read() -> None:
    """Five tables, not the original two. `projects`, `findings` and
    `analysis_jobs` arrived with ADR 0014, and a provisioner that creates
    three of five fails on the first read of the other two."""
    client = RecordingChClient()

    load_script().create_tables(client)

    joined = "\n".join(client.commands)
    creates = [cmd for cmd in client.commands if cmd.startswith("CREATE TABLE")]
    assert len(creates) == 5
    for table in ALL_TABLES:
        assert table in joined, table


def test_widens_a_table_an_earlier_run_already_created() -> None:
    """`CREATE TABLE IF NOT EXISTS` says nothing to a table that exists, so a
    column added to one of the five never reaches a deployment that ran the
    previous version. The provisioner issues the additions too, or the column
    exists only for deployments provisioned after it was written."""
    client = RecordingChClient()

    load_script().create_tables(client)

    additions = [cmd for cmd in client.commands if cmd.startswith("ALTER TABLE")]
    assert additions == list(schema_module().ALTERATIONS)


def test_every_statement_is_idempotent() -> None:
    """A second run is a no-op, like both provisioning shell scripts.

    Without `IF NOT EXISTS` the second run fails on an existing table or an
    existing column, which turns re-provisioning into a manual repair.
    """
    client = RecordingChClient()

    load_script().create_tables(client)

    for statement in client.commands:
        assert "IF NOT EXISTS" in statement, statement


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


def test_dry_run_prints_the_ddl_without_connecting() -> None:
    """`--dry-run` matches the two shell scripts: show the work, touch nothing.

    It also needs no credentials, so it is the one path a reviewer can run on
    a machine with no ClickHouse account.
    """
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("CREATE TABLE IF NOT EXISTS") == 5
    assert "DROP TABLE" not in result.stdout
    for table in ALL_TABLES:
        assert table in result.stdout, table


# --- The destructive path (ADR 0014) ----------------------------------------
#
# ClickHouse cannot re-key a MergeTree in place: ORDER BY is part of the
# table's physical layout. Re-keying `tracker_items` and `script_versions`
# therefore means dropping them, which takes the deployed demo project's
# clearance state with it. That is a decision for a human, so the script
# refuses to make it on its own.


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
        check=False,
    )


def test_recreate_drops_every_table_before_creating_it() -> None:
    client = RecordingChClient()

    load_script().recreate_tables(client)

    drops = [cmd for cmd in client.commands if cmd.startswith("DROP TABLE")]
    creates = [cmd for cmd in client.commands if cmd.startswith("CREATE TABLE")]
    assert len(drops) == 5
    assert len(creates) == 5
    for table in ALL_TABLES:
        drop_index = next(
            i
            for i, cmd in enumerate(client.commands)
            if cmd.strip() == f"DROP TABLE IF EXISTS {table}"
        )
        create_index = next(
            i
            for i, cmd in enumerate(client.commands)
            if cmd.startswith(f"CREATE TABLE IF NOT EXISTS {table}")
        )
        assert drop_index < create_index, table


def test_recreate_without_force_destroys_nothing() -> None:
    """The guard is in `main`, not in `recreate_tables`, so this exercises the
    entry point a human actually types."""
    result = _run("--recreate")

    assert result.returncode != 0
    assert "DROP TABLE" not in result.stdout


def test_recreate_without_force_names_every_table_it_would_destroy() -> None:
    """A refusal that does not say what is at stake is a refusal a human
    re-runs with the override without reading it."""
    result = _run("--recreate")

    printed = result.stdout + result.stderr
    for table in ALL_TABLES:
        assert table in printed, table
    assert "--force" in printed


def test_the_override_alone_is_refused_rather_than_ignored() -> None:
    """Typing the override alone reads as "I have armed the destructive
    path". Silently doing the safe thing leaves the operator believing they
    ran a migration they did not."""
    result = _run("--force")

    assert result.returncode != 0
    assert "--recreate" in result.stdout + result.stderr


def test_recreate_dry_run_prints_the_drops_and_the_creates() -> None:
    """The one rehearsal a reviewer can run with no ClickHouse account: it
    connects to nothing and shows exactly the statements a real run issues."""
    result = _run("--recreate", "--force", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("DROP TABLE IF EXISTS") == 5
    assert result.stdout.count("CREATE TABLE IF NOT EXISTS") == 5
    for table in ALL_TABLES:
        assert table in result.stdout, table


def test_recreate_dry_run_without_the_override_still_refuses() -> None:
    """`--dry-run` shows what a real run would do, so it has to show the
    refusal too. Printing the migration here would tell the operator the
    command works, and the real run would then refuse."""
    result = _run("--recreate", "--dry-run")

    assert result.returncode != 0
    assert "DROP TABLE" not in result.stdout
