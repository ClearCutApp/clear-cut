"""Hand-written stand-ins for the ClickHouse client boundary (AGENT.md
Section 5).

The real `clickhouse_connect.driver.client.Client` opens an HTTPS connection
at construction, so every store in `adapters/clickhouse/` is unit-tested
against these instead. They live in their own module rather than in one
store's test file because five stores share the same three-method boundary
(`command`, `insert`, `query`), and a test importing another test file to
borrow its fake couples the two suites for no reason.

No `unittest.mock`, no network, no live ClickHouse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeQueryResult:
    """Stands in for `clickhouse_connect.driver.query.QueryResult`, whose
    `result_rows` attribute is the only part these adapters read."""

    result_rows: list[tuple[Any, ...]] = field(default_factory=list)


class FakeChClient:
    """Records every `command`, `insert`, and `query` call it receives, and
    returns a canned `FakeQueryResult` set by the test via `set_result`."""

    def __init__(self) -> None:
        self.commands: list[str] = []
        self.inserts: list[tuple[str, list[list[Any]], list[str]]] = []
        self.queries: list[tuple[str, dict[str, Any] | None]] = []
        self._next_result = FakeQueryResult()

    def set_result(self, rows: list[tuple[Any, ...]]) -> None:
        self._next_result = FakeQueryResult(result_rows=rows)

    def command(self, cmd: str) -> str:
        self.commands.append(cmd)
        return "ok"

    def insert(self, table: str, data: list[list[Any]], column_names: list[str]) -> None:
        self.inserts.append((table, data, column_names))

    def query(self, query: str, parameters: dict[str, Any] | None = None) -> FakeQueryResult:
        self.queries.append((query, parameters))
        return self._next_result


class ExplodingChClient:
    """Raises a real `clickhouse_connect` driver error on every call.

    The error is a real driver type, not a bare `Exception`: the adapters
    translate whatever the SDK raises into a domain error (D23), and a stand-in
    exception would let a translation that only catches its own test's type
    pass.
    """

    def command(self, cmd: str) -> str:
        from clickhouse_connect.driver.exceptions import DatabaseError

        raise DatabaseError("simulated ClickHouse failure")

    def insert(self, table: str, data: list[list[Any]], column_names: list[str]) -> None:
        from clickhouse_connect.driver.exceptions import DatabaseError

        raise DatabaseError("simulated ClickHouse failure")

    def query(self, query: str, parameters: dict[str, Any] | None = None) -> FakeQueryResult:
        from clickhouse_connect.driver.exceptions import DatabaseError

        raise DatabaseError("simulated ClickHouse failure")
