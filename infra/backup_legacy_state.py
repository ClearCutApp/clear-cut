"""Resumable raw ClickHouse backup; default verifies local files without cloud calls."""

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from infra.migration_snapshot import MAX_ROW_BYTES, TABLE_KEYS, canonical, digest_file, rows, verify


def save_manifest(directory: Path, manifest: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile(mode="wb", dir=directory, delete=False) as output:
        output.write(canonical(manifest))
        output.flush()
        os.fsync(output.fileno())
        temporary = output.name
    os.replace(temporary, directory / "manifest.json")


def source_rows(client: Any, table: str, project_ids: list[str]) -> Iterator[dict[str, Any]]:
    if table not in TABLE_KEYS:
        raise ValueError("unknown legacy table")
    query = f"SELECT * FROM {table} WHERE project_id IN {{project_ids:Array(String)}}"
    with client.query_rows_stream(
        query,
        parameters={"project_ids": project_ids},
        query_tz="UTC",
        tz_mode="aware",
        settings={"max_execution_time": 300},
    ) as result:
        columns = result.source.column_names
        if len(set(columns)) != len(columns) or not set(TABLE_KEYS[table]) <= set(columns):
            raise ValueError("legacy source identity columns do not match the expected schema")
        for values in result:
            record = dict(zip(columns, values, strict=True))
            if record.get("project_id") not in project_ids:
                raise ValueError("source returned a record outside the selected legacy projects")
            yield record


def backup(
    client: Any, directory: Path, project_ids: list[str], source_identity_sha256: str
) -> dict[str, Any]:
    if not project_ids or len(set(project_ids)) != len(project_ids):
        raise ValueError("explicit unique legacy project IDs are required")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / "manifest.json"
    if path.exists():
        manifest = json.loads(path.read_bytes())
        if (
            manifest.get("schema_version") != 1
            or manifest.get("project_ids") != sorted(project_ids)
            or manifest.get("source_identity_sha256") != source_identity_sha256
        ):
            raise ValueError("existing backup belongs to a different source or project scope")
    else:
        manifest = {
            "schema_version": 1,
            "project_ids": sorted(project_ids),
            "source_identity_sha256": source_identity_sha256,
            "source_query": "raw_without_FINAL",
            "created_at": datetime.now(UTC).isoformat(),
            "quiescence": "operator_asserted_not_independently_verified",
            "tables": {},
        }
        save_manifest(directory, manifest)
    for table in TABLE_KEYS:
        target = directory / (table + ".jsonl")
        existing = manifest["tables"].get(table)
        if existing:
            digest, size = digest_file(target)
            if digest != existing["sha256"] or size != existing["size_bytes"]:
                raise ValueError("completed backup table changed; refusing to overwrite evidence")
            continue
        if target.exists():
            captured = Counter(hashlib.sha256(canonical(row)).hexdigest() for row in rows(target))
            current = Counter(
                hashlib.sha256(canonical(row)).hexdigest()
                for row in source_rows(client, table, project_ids)
            )
            if captured != current:
                raise ValueError(
                    "unacknowledged backup differs from the source; "
                    "preserve both for reconciliation"
                )
            digest, size = digest_file(target)
            manifest["tables"][table] = {
                "file": target.name,
                "rows": sum(captured.values()),
                "sha256": digest,
                "size_bytes": size,
            }
            save_manifest(directory, manifest)
            continue
        count = 0
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=directory, prefix=table + ".partial-", delete=False
        ) as output:
            for record in source_rows(client, table, project_ids):
                line = canonical(record) + b"\n"
                if len(line) > MAX_ROW_BYTES:
                    raise ValueError("legacy record exceeds the explicit backup limit")
                output.write(line)
                count += 1
            output.flush()
            os.fsync(output.fileno())
            temporary = output.name
        os.replace(temporary, target)
        digest, size = digest_file(target)
        manifest["tables"][table] = {
            "file": target.name,
            "rows": count,
            "sha256": digest,
            "size_bytes": size,
        }
        save_manifest(directory, manifest)
    return verify(directory)


def verify_source(client: Any, directory: Path, source_identity_sha256: str) -> dict[str, Any]:
    report = verify(directory)
    manifest = json.loads((directory / "manifest.json").read_bytes())
    if manifest["source_identity_sha256"] != source_identity_sha256:
        raise ValueError("source identity changed")
    changed = []
    for table in TABLE_KEYS:
        captured = Counter(
            hashlib.sha256(canonical(row)).hexdigest()
            for row in rows(directory / (table + ".jsonl"))
        )
        current = Counter(
            hashlib.sha256(canonical(row)).hexdigest()
            for row in source_rows(client, table, manifest["project_ids"])
        )
        if captured != current:
            changed.append(table)
    return {
        **report,
        "source_rechecked_at": datetime.now(UTC).isoformat(),
        "source_changed_tables": changed,
        "source_unchanged_at_recheck": not changed,
        "publication_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--export", action="store_true")
    mode.add_argument("--verify-source", action="store_true")
    parser.add_argument("--legacy-project", action="append", default=[])
    parser.add_argument(
        "--source-quiesced",
        action="store_true",
        help="Records the operator's assertion that legacy writes and workers are stopped",
    )
    parser.add_argument("--database", default="default")
    args = parser.parse_args()
    if not args.export and not args.verify_source:
        print(json.dumps(verify(args.directory), indent=2))
        return
    if args.export and (not args.source_quiesced or not args.legacy_project):
        parser.error("export requires explicit legacy projects and a quiesced-source assertion")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", args.database):
        parser.error("invalid source database")
    from clickhouse_connect import get_client

    from clearcut.adapters.clickhouse.client import bare_host

    host, user, password = (
        os.environ[key] for key in ("CLICKHOUSE_HOST", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD")
    )
    identity = hashlib.sha256(
        canonical({"host": host, "user": user, "database": args.database})
    ).hexdigest()
    client = get_client(
        host=bare_host(host),
        username=user,
        password=password,
        database=args.database,
        secure=True,
        connect_timeout=10,
        send_receive_timeout=60,
        query_retries=0,
    )
    try:
        report = (
            backup(client, args.directory, args.legacy_project, identity)
            if args.export
            else verify_source(client, args.directory, identity)
        )
        print(json.dumps(report, indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "legacy backup could not be verified; preserve files and inspect the receipt"
        ) from None
