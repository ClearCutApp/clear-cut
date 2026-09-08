"""Inspect the additive ClickHouse analytics DDL; --apply creates only this table."""

import argparse
import os
from typing import cast

import clickhouse_connect

from clearcut.adapters.clickhouse.activity import DDL, ClickHouseActivity
from clearcut.adapters.clickhouse.client import _ChClient, bare_host


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="Execute additive CREATE IF NOT EXISTS."
    )
    args = parser.parse_args()
    if not args.apply:
        print(DDL.strip())
        return
    client = cast(
        _ChClient,
        clickhouse_connect.get_client(
            host=bare_host(os.environ["CLICKHOUSE_HOST"]),
            username=os.environ["CLICKHOUSE_USER"],
            password=os.environ["CLICKHOUSE_PASSWORD"],
            secure=True,
            connect_timeout=10,
            send_receive_timeout=30,
            query_retries=0,
        ),
    )
    ClickHouseActivity(client).ensure_schema()
    print("analytics_events table create completed; verify schema and real delivery separately.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "activity schema operation failed; no legacy tables were changed"
        ) from None
