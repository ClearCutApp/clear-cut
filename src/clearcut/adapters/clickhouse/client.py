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


def bare_host(configured: str) -> str:
    """The bare hostname `clickhouse_connect` wants, from whatever was pasted.

    The Cloud console's Connect panel shows a full URL, and
    `get_client(host=...)` prepends the scheme itself, so pasting that value
    verbatim produces `https://https://host:8443` and fails DNS resolution on
    the literal string "https". Seen on the first real connection attempt
    (2026-09-03, CP-055), and again on 2026-09-06 from
    `infra/provision_tracker_schema.py`, which read the same variable raw.

    It lives here rather than in `composition.py` because the console is where
    every operator copies from, and the entry points that read this variable
    are the application, the provisioning scripts and the live tier. One of
    them normalising is the same defect as none of them doing it.
    """
    host = configured.strip()
    if "://" in host:
        host = host.split("://", 1)[1]
    return host.split("/", 1)[0].split(":", 1)[0]
