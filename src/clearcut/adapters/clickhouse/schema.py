"""The DDL every store in this package reads and writes against, and the
routine that issues it (CP-062, `.claude/CHECKPOINTS.md`).

`tracker_items` is a `ReplacingMergeTree` keyed on `item_id` and versioned by
each row's `version` column, matching `TrackerItem`'s own frozen, versioned
design (`domain/tracker.py`): every state transition is a new row, never a
mutation, so the table's latest-wins read always resolves to the last
producer action. `script_versions` follows the same shape, keyed on
`project_id`, so `latest_script` resolves to the newest uploaded version
without a live schema read.

`ensure_schema` is not repeated per store. It holds the only copy of the DDL,
so `infra/provision_tracker_schema.py` and every store's own `ensure_schema`
method issue the exact same statements.
"""

from __future__ import annotations

from clearcut.adapters.clickhouse import client as ch_client

_TRACKER_ITEMS_DDL = """\
CREATE TABLE IF NOT EXISTS tracker_items (
    item_id String,
    project_id String,
    finding_id String,
    scene_numbers Array(UInt32),
    state String,
    needs_review UInt8,
    required_document String,
    contact String,
    litigation_posture String,
    draft_email Nullable(String),
    note String,
    updated_at String,
    version UInt32
) ENGINE = ReplacingMergeTree(version)
ORDER BY item_id
"""

_SCRIPT_VERSIONS_DDL = """\
CREATE TABLE IF NOT EXISTS script_versions (
    script_id String,
    project_id String,
    version UInt32,
    gcs_uri String,
    jurisdiction_code String,
    scenes String
) ENGINE = ReplacingMergeTree(version)
ORDER BY project_id
"""

DDL = (_TRACKER_ITEMS_DDL, _SCRIPT_VERSIONS_DDL)


def ensure_schema(client: ch_client._ChClient) -> None:
    try:
        for statement in DDL:
            client.command(statement)
    except Exception as exc:
        raise ch_client.ClickHouseUnavailable(f"failed to create tables: {exc}") from exc
