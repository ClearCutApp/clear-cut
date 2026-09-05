"""The DDL the whole package shares (`adapters/clickhouse/schema.py`).

Each store's own test asserts the key its table is sorted on. These assert
what only the collection can: that the create list, the drop list and the
table-name list describe one schema, since `infra/provision_tracker_schema.py
--recreate` reads all three and a table named in one but not another is a
table it drops without recreating, or provisions and never drops.
"""

from __future__ import annotations

from clearcut.adapters.clickhouse import schema
from tests.unit.adapters.fake_ch_client import FakeChClient


def test_every_named_table_has_a_create_statement() -> None:
    for table in schema.TABLES:
        assert any(
            statement.startswith(f"CREATE TABLE IF NOT EXISTS {table}") for statement in schema.DDL
        ), table


def test_every_create_statement_belongs_to_a_named_table() -> None:
    """The other direction. A table created and never named is a table
    `--recreate` leaves standing with its old key, which is the exact defect
    ADR 0014 exists to fix."""
    assert len(schema.DDL) == len(schema.TABLES)


def test_every_named_table_has_a_drop_statement() -> None:
    assert schema.DROP_DDL == tuple(f"DROP TABLE IF EXISTS {table}" for table in schema.TABLES)


def test_ensure_schema_issues_the_creates_and_never_a_drop() -> None:
    """Every store calls `ensure_schema` on a live connection. A drop reaching
    that path would empty the tables on a redeploy."""
    client = FakeChClient()

    schema.ensure_schema(client)

    assert client.commands == list(schema.DDL)
    assert not any("DROP" in statement for statement in client.commands)
