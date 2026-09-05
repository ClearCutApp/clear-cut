"""The ClickHouse client boundary shared by every store in this package
(CP-062, `.claude/CHECKPOINTS.md`).

`_ChClient` is a narrow local `Protocol` covering only the three
`clickhouse_connect` client methods any store in this package calls, rather
than the concrete `Client` class -- the same pattern `BigQueryLoreStore`
uses, so a hand-written unit-test fake never needs to open a real HTTPS
connection (AGENT.md Section 5).

`ClickHouseUnavailable` is the one error every store in this package raises
when the client fails to execute a command, insert, or query. It lives here,
not in a per-table module, so a future store shares the same type its
sibling stores already raise instead of minting its own.
"""

from __future__ import annotations

from typing import Any, Protocol

from clearcut.domain.errors import SourceUnavailable


class ClickHouseUnavailable(SourceUnavailable):
    """The ClickHouse client failed to execute a command, insert, or query."""


class _QueryResult(Protocol):
    """The subset of `clickhouse_connect.driver.query.QueryResult` this
    package reads."""

    result_rows: list[tuple[Any, ...]]


class _ChClient(Protocol):
    """The subset of `clickhouse_connect.driver.client.Client` this package
    calls."""

    def command(self, cmd: str) -> object: ...

    def insert(self, table: str, data: list[list[Any]], column_names: list[str]) -> object: ...

    def query(self, query: str, parameters: dict[str, Any] | None = None) -> _QueryResult: ...
