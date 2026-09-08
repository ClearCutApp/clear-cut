"""Verify immutable legacy backups without inventing ownership or lost history."""

import hashlib
import json
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TABLE_KEYS = {
    "projects": ("project_id",),
    "script_versions": ("project_id", "script_id"),
    "findings": ("project_id", "script_id", "finding_id"),
    "tracker_items": ("project_id", "item_id", "version"),
    "analysis_jobs": ("project_id", "analysis_id", "version"),
}
MAX_ROW_BYTES = 64 * 1024 * 1024


def canonical(value: Any) -> bytes:
    def encode(item: Any) -> str:
        if isinstance(item, datetime) and item.tzinfo is not None:
            return item.astimezone(UTC).isoformat(timespec="microseconds")
        raise ValueError("unsupported or timezone-naive backup value")

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=encode,
    ).encode()


def digest_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def rows(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("rb") as source:
        while line := source.readline(MAX_ROW_BYTES + 1):
            if len(line) > MAX_ROW_BYTES:
                raise ValueError("legacy backup row exceeds the explicit 64 MiB limit")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("legacy backup rows must be objects")
            yield value


def verify(directory: Path) -> dict[str, Any]:
    manifest = json.loads((directory / "manifest.json").read_bytes())
    if manifest.get("schema_version") != 1 or set(manifest.get("tables", {})) != set(TABLE_KEYS):
        raise ValueError("legacy backup is incomplete or has an unsupported schema")
    scope = manifest.get("project_ids")
    if (
        not isinstance(scope, list)
        or not scope
        or any(not isinstance(value, str) or not value for value in scope)
    ):
        raise ValueError("an explicit legacy project scope is required")
    counts, logical_counts, table_hashes = {}, {}, {}
    issues: list[dict[str, Any]] = []
    projects: set[str] = set()
    scripts: set[tuple[str, str]] = set()
    finding_links: set[tuple[str, str]] = set()
    finding_ids: set[tuple[str, str]] = set()
    tracker_links: set[tuple[str, str]] = set()
    job_links: set[tuple[str, str]] = set()
    incomplete_jobs: list[dict[str, str]] = []
    analysis_projects: dict[str, set[str]] = {}
    maximum_script_version: dict[str, int] = {}
    latest_script_ids: dict[str, set[str]] = {}
    for table, key_fields in TABLE_KEYS.items():
        entry = manifest["tables"][table]
        if entry.get("file") != table + ".jsonl":
            raise ValueError("unexpected backup file path")
        path = directory / entry["file"]
        digest, size = digest_file(path)
        if digest != entry.get("sha256") or size != entry.get("size_bytes"):
            raise ValueError("legacy backup integrity check failed")
        identities: dict[tuple[Any, ...], Counter[str]] = {}
        count = 0
        for row in rows(path):
            project_id = row.get("project_id")
            if not isinstance(project_id, str) or project_id not in scope:
                raise ValueError("backup contains a project outside the authorized scope")
            try:
                key = tuple(row[field] for field in key_fields)
            except KeyError:
                raise ValueError("backup row is missing its original identity") from None
            if any(
                (type(value) is not int or value < 1)
                if field == "version"
                else (
                    not isinstance(value, str)
                    or not value
                    or "/" in value
                    or len(value.encode()) > 128
                )
                for field, value in zip(key_fields, key, strict=True)
            ):
                raise ValueError("invalid legacy identity or version; IDs must not be renamed")
            payload_hash = hashlib.sha256(canonical(row)).hexdigest()
            identities.setdefault(key, Counter())[payload_hash] += 1
            count += 1
            if table == "projects":
                projects.add(project_id)
            if table == "script_versions":
                scripts.add((project_id, row["script_id"]))
                version = row.get("version")
                if type(version) is not int or version < 1:
                    raise ValueError("legacy script version must be positive")
                previous = maximum_script_version.get(project_id, 0)
                if version > previous:
                    maximum_script_version[project_id] = version
                    latest_script_ids[project_id] = {row["script_id"]}
                elif version == previous:
                    latest_script_ids[project_id].add(row["script_id"])
            if table == "findings":
                finding_links.add((project_id, row["script_id"]))
                finding_ids.add((project_id, row["finding_id"]))
            if table == "tracker_items":
                tracker_links.add((project_id, row.get("finding_id", "")))
            if table == "analysis_jobs":
                if row.get("state") == "SUCCEEDED":
                    job_links.add((project_id, row.get("script_id", "")))
                else:
                    incomplete_jobs.append(
                        {
                            "project_id": project_id,
                            "analysis_id": row["analysis_id"],
                            "source_state": row.get("state", "unknown"),
                        }
                    )
                analysis_projects.setdefault(row["analysis_id"], set()).add(project_id)
        if digest_file(path) != (digest, size):
            raise ValueError("legacy backup changed during verification")
        if count != entry.get("rows"):
            raise ValueError("legacy backup row count mismatch")
        for key, hashes in identities.items():
            if len(hashes) > 1:
                issues.append(
                    {
                        "code": "conflicting_same_identity",
                        "table": table,
                        "identity": list(key),
                        "payload_hashes": sorted(hashes),
                    }
                )
        table_hashes[table] = hashlib.sha256(
            canonical(
                sorted((list(key), sorted(hashes.items())) for key, hashes in identities.items())
            )
        ).hexdigest()
        counts[table], logical_counts[table] = count, len(identities)
    for project_id in set(scope) - projects:
        issues.append({"code": "missing_project", "project_id": project_id})
    for project_id, script_id in (finding_links | job_links) - scripts:
        issues.append({"code": "missing_script", "project_id": project_id, "script_id": script_id})
    for project_id, finding_id in tracker_links - finding_ids:
        issues.append(
            {"code": "missing_finding", "project_id": project_id, "finding_id": finding_id}
        )
    for analysis_id, projects_for_id in analysis_projects.items():
        if len(projects_for_id) > 1:
            issues.append(
                {
                    "code": "analysis_id_cross_project_collision",
                    "analysis_id": analysis_id,
                    "project_ids": sorted(projects_for_id),
                }
            )
    for project_id, identifiers in latest_script_ids.items():
        if len(identifiers) > 1:
            issues.append(
                {
                    "code": "ambiguous_latest_script",
                    "project_id": project_id,
                    "script_ids": sorted(identifiers),
                }
            )
    return {
        "schema_version": 1,
        "manifest_sha256": hashlib.sha256(canonical(manifest)).hexdigest(),
        "status": "blocked" if issues else "records_reconciled",
        "project_ids": scope,
        "raw_rows": counts,
        "logical_rows": logical_counts,
        "table_multiset_sha256": table_hashes,
        "maximum_script_version": maximum_script_version,
        "issues": issues,
        "incomplete_jobs_preserved_without_relaunch": incomplete_jobs,
        "legacy_audit_history_complete": False,
        "ownership_verified": False,
        "original_objects_verified": False,
        "publication_allowed": False,
    }
