#!/usr/bin/env python3
"""Create ClickHouse's two tracker tables (docs/plan/infrastructure.md Section 6).

`ClickHouseTrackerStore.ensure_schema()` had no caller outside its own unit
test, so `tracker_items` and `script_versions` were never created and the first
live write would have failed on a missing table.

This lives in `infra/` rather than in `create_app()` on purpose. Creating a
table is provisioning, and `tests/unit/test_composition.py` asserts that
building the adapter graph opens no socket -- issuing DDL at startup would
trade that invariant away to solve a problem provisioning already owns. It also
means a redeploy does not re-run DDL on every cold start.

Usage:
    .venv/bin/python infra/provision_tracker_schema.py [--dry-run]

It reuses the adapter's DDL rather than repeating it, so it needs the project's
dependencies -- a bare `python3` will not do.

--dry-run prints the exact statements a real run would issue and connects to
nothing, so it needs no credentials. Both statements are `CREATE TABLE IF NOT
EXISTS`, so a real run is idempotent the same way the two shell scripts are.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, cast

# Run standalone (no PYTHONPATH set), so this adds the repo's src/ to sys.path
# the same way pyproject.toml's pytest pythonpath does for tests.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

try:
    from clearcut.adapters.clickhouse.client import _ChClient  # noqa: E402
    from clearcut.adapters.clickhouse.tracker import ClickHouseTrackerStore  # noqa: E402
except ModuleNotFoundError as exc:  # pragma: no cover - depends on the interpreter
    # Unlike build_manifest.py, which touches only the stdlib-only domain layer,
    # this script reuses the adapter's DDL so the schema has exactly one
    # definition. That means it needs the project's dependencies, and the
    # `#!/usr/bin/env python3` shebang finds a system interpreter without them.
    print(
        f"provision_tracker_schema.py: {exc.name} is not importable.\n"
        "Run it with the project interpreter:\n"
        "    .venv/bin/python infra/provision_tracker_schema.py --dry-run",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

REQUIRED = ("CLICKHOUSE_HOST", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD")


def create_tables(client: Any) -> None:
    """Issue both DDL statements through the adapter that owns them.

    The DDL is not repeated here. `ensure_schema()` holds the only copy, so
    this script cannot drift from the schema the adapter reads and writes --
    which is exactly the failure mode `test_identifier_agreement.py` exists to
    catch one layer up.
    """
    ClickHouseTrackerStore(cast(_ChClient, client)).ensure_schema()


class _PrintingClient:
    """Prints each statement instead of executing it.

    Dry-run drives the same `ensure_schema()` the real run drives, so what it
    shows cannot fall out of step with what it would do.
    """

    def command(self, statement: str) -> None:
        print(statement.strip())
        print()


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
        create_tables(_PrintingClient())
        return 0

    missing = _missing_credentials()
    if missing:
        print(
            f"provision_tracker_schema.py: missing required environment {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    import clickhouse_connect

    client = clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        username=os.environ["CLICKHOUSE_USER"],
        password=os.environ["CLICKHOUSE_PASSWORD"],
        secure=True,
    )
    create_tables(client)
    print("created tracker_items and script_versions (or left them as they were)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
