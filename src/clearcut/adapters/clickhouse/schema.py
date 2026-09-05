"""The DDL every store in this package reads and writes against, and the
routine that issues it (CP-062, `.claude/CHECKPOINTS.md`).

Every `ORDER BY` here starts at `project_id`, because the ids below a project
are unique only inside one. Item ids are `EVT-NNN`, minted per analysis, so
two projects produce the same string; a key that omits the project makes
those the same row and the next background merge keeps one and drops the
other without erroring (ADR 0014).

`tracker_items` stays a `ReplacingMergeTree(version)`: `TrackerItem` is
frozen and versioned (`domain/tracker.py`), so a state transition writes a
new row and latest-wins is the read a producer wants. `script_versions` drops
the version argument, because a script version is a distinct row to keep
rather than an older copy of one -- collapsing it left a single row per
project and nothing for the delta path to diff against.

`analysis_jobs.created_at` and `updated_at` are `DateTime64(3, 'UTC')` rather
than the ISO strings `tracker_items.updated_at` holds. `AnalysisJob.is_stale`
subtracts two datetimes, so a string column would put a parse -- and a date
format -- on every read; the millisecond precision is what the column stores,
and the store rounds to it on the way in.

`ensure_schema` is not repeated per store. It holds the only copy of the DDL,
so `infra/provision_tracker_schema.py` and every store's own `ensure_schema`
method issue the exact same five statements.
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
ORDER BY (project_id, item_id)
"""

_SCRIPT_VERSIONS_DDL = """\
CREATE TABLE IF NOT EXISTS script_versions (
    script_id String,
    project_id String,
    version UInt32,
    gcs_uri String,
    jurisdiction_code String,
    scenes String
) ENGINE = ReplacingMergeTree
ORDER BY (project_id, script_id)
"""

_PROJECTS_DDL = """\
CREATE TABLE IF NOT EXISTS projects (
    project_id String,
    title String,
    jurisdiction_code String,
    created_at String
) ENGINE = ReplacingMergeTree
ORDER BY project_id
"""

_FINDINGS_DDL = """\
CREATE TABLE IF NOT EXISTS findings (
    project_id String,
    script_id String,
    finding_id String,
    scene_number UInt32,
    page UInt32,
    raw_text String,
    category String,
    ner_label Nullable(String),
    risk_level String,
    required_document String,
    citations String,
    contradicts Nullable(String)
) ENGINE = ReplacingMergeTree
ORDER BY (project_id, script_id, finding_id)
"""

_ANALYSIS_JOBS_DDL = """\
CREATE TABLE IF NOT EXISTS analysis_jobs (
    analysis_id String,
    project_id String,
    script_id String,
    state String,
    created_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC'),
    error String,
    version UInt32
) ENGINE = ReplacingMergeTree(version)
ORDER BY (project_id, analysis_id)
"""

TABLES = ("tracker_items", "script_versions", "projects", "findings", "analysis_jobs")

DDL = (
    _TRACKER_ITEMS_DDL,
    _SCRIPT_VERSIONS_DDL,
    _PROJECTS_DDL,
    _FINDINGS_DDL,
    _ANALYSIS_JOBS_DDL,
)


def ensure_schema(client: ch_client._ChClient) -> None:
    try:
        for statement in DDL:
            client.command(statement)
    except Exception as exc:
        raise ch_client.ClickHouseUnavailable(f"failed to create tables: {exc}") from exc
