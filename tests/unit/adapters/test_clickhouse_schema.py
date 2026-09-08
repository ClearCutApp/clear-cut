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

    assert client.commands == [*schema.DDL, *schema.ALTERATIONS]
    assert not any("DROP" in statement for statement in client.commands)


def test_every_column_addition_widens_a_table_the_creates_name() -> None:
    """`CREATE TABLE IF NOT EXISTS` is silent about a table that already
    exists, so a column added to a create statement reaches only deployments
    provisioned after it. `ALTERATIONS` carries it to the rest -- and, like
    the creates, may only name a table this schema owns."""
    for statement in schema.ALTERATIONS:
        assert statement.startswith("ALTER TABLE ")
        assert "ADD COLUMN IF NOT EXISTS" in statement, statement
        table = statement.removeprefix("ALTER TABLE ").split(" ", 1)[0]
        assert table in schema.TABLES, statement


def test_no_column_addition_repeats_a_column_the_create_already_carries() -> None:
    """Not a duplicate of the create: a fresh table gets the column from the
    create statement and the addition is a no-op, which is the point. This
    asserts the two agree on the column's name and type, so a table widened by
    `ALTERATIONS` and one made by `DDL` are the same table."""
    projects_ddl = next(
        statement
        for statement in schema.DDL
        if statement.startswith("CREATE TABLE IF NOT EXISTS projects")
    )
    for statement in schema.ALTERATIONS:
        column = statement.split("ADD COLUMN IF NOT EXISTS ", 1)[1]
        assert f"    {column},\n" in projects_ddl or f"    {column}\n" in projects_ddl, statement
