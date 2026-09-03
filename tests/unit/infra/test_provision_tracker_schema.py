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


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("provision_tracker_schema", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def test_creates_both_tracker_tables() -> None:
    client = RecordingChClient()

    load_script().create_tables(client)

    assert len(client.commands) == 2
    joined = "\n".join(client.commands)
    assert "tracker_items" in joined
    assert "script_versions" in joined


def test_every_statement_is_idempotent() -> None:
    """A second run is a no-op, like both provisioning shell scripts.

    Without `IF NOT EXISTS` the second run fails on an existing table, which
    turns re-provisioning into a manual repair.
    """
    client = RecordingChClient()

    load_script().create_tables(client)

    for statement in client.commands:
        assert "CREATE TABLE IF NOT EXISTS" in statement, statement


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
    assert result.stdout.count("CREATE TABLE IF NOT EXISTS") == 2
    assert "tracker_items" in result.stdout
    assert "script_versions" in result.stdout
