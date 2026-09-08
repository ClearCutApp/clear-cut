"""Inspect or add the recovery runtime indexes without replacing existing indexes."""

import argparse
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

INDEXES = tuple(
    (collection, field)
    for collection in ("analysis_jobs", "outbox", "lore_outbox", "notification_outbox")
    for field in ("available_at", "lease_until")
)
Runner = Callable[[list[str]], Any]


def command(args: list[str]) -> Any:
    result = subprocess.run(args, capture_output=True, text=True, timeout=120, check=False)
    if result.returncode:
        raise RuntimeError("gcloud index operation failed; no retry was attempted")
    try:
        return json.loads(result.stdout or "null")
    except ValueError:
        raise RuntimeError("gcloud index response could not be verified") from None


def create_command(project: str, collection: str, field: str) -> list[str]:
    return [
        "gcloud",
        "firestore",
        "indexes",
        "composite",
        "create",
        "--project",
        project,
        "--database",
        "(default)",
        "--collection-group",
        collection,
        "--query-scope",
        "collection",
        "--field-config",
        "field-path=state,order=ascending",
        "--field-config",
        f"field-path={field},order=ascending",
        "--async",
        "--format=json",
        "--quiet",
    ]


def inspect(project: str, run: Runner = command) -> dict[tuple[str, str], dict[str, Any]]:
    values = run(
        [
            "gcloud",
            "firestore",
            "indexes",
            "composite",
            "list",
            "--project",
            project,
            "--database",
            "(default)",
            "--format=json",
            "--quiet",
        ]
    )
    if not isinstance(values, list):
        raise RuntimeError("index inventory did not return a list")
    matched = {}
    prefix = f"projects/{project}/databases/(default)/collectionGroups/"
    for value in values:
        name = value.get("name", "")
        if not name.startswith(prefix) or value.get("queryScope") != "COLLECTION":
            continue
        collection = name[len(prefix) :].split("/")[0]
        fields = [
            (field.get("fieldPath"), field.get("order"))
            for field in value.get("fields", [])
            if field.get("fieldPath") != "__name__"
        ]
        for expected_collection, field in INDEXES:
            if collection == expected_collection and fields == [
                ("state", "ASCENDING"),
                (field, "ASCENDING"),
            ]:
                matched[(collection, field)] = value
    return matched


def reconcile(
    project: str,
    *,
    apply: bool,
    run: Runner = command,
    journal: dict[str, Any] | None = None,
    persist: Callable[[dict[str, Any]], None] = lambda value: None,
) -> list[dict[str, Any]]:
    existing = inspect(project, run)
    journal = journal if journal is not None else {}
    result = []
    for collection, field in INDEXES:
        index = existing.get((collection, field))
        if index:
            state = index.get("state", "UNKNOWN")
            if state not in {"READY", "CREATING"}:
                raise RuntimeError(f"index {collection}/{field} requires manual repair")
            result.append(
                {"collection": collection, "field": field, "state": state, "name": index["name"]}
            )
        elif apply:
            key = collection + "/" + field
            if key in journal:
                result.append(
                    {"collection": collection, "field": field, "state": "SUBMISSION_UNRESOLVED"}
                )
                continue
            journal[key] = {"state": "submission_unknown"}
            persist(journal)
            operation = run(create_command(project, collection, field))
            journal[key] = {"state": "submitted", "operation": operation}
            persist(journal)
            result.append(
                {
                    "collection": collection,
                    "field": field,
                    "state": "SUBMITTED_UNVERIFIED",
                    "operation": operation,
                }
            )
        else:
            result.append({"collection": collection, "field": field, "state": "MISSING"})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply", action="store_true", help="Inspect and submit missing additive indexes"
    )
    mode.add_argument(
        "--verify", action="store_true", help="Read cloud inventory and require every index READY"
    )
    parser.add_argument(
        "--receipt", type=Path, help="Required durable submission receipt for --apply"
    )
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", args.project):
        parser.error("invalid GCP project identifier")
    if not args.apply and not args.verify:
        print(
            json.dumps(
                {
                    "commands": [create_command(args.project, *index) for index in INDEXES],
                    "cloud_calls": False,
                },
                indent=2,
            )
        )
        return
    if args.apply and args.receipt is None:
        parser.error("--apply requires a receipt path; ambiguous submissions must not be repeated")
    journal: dict[str, Any] = {}
    if args.receipt and args.receipt.exists():
        saved = json.loads(args.receipt.read_text())
        if saved.get("project") != args.project or saved.get("schema_version") != 1:
            parser.error("receipt belongs to a different project or schema")
        journal = saved["submissions"]

    def persist(values: dict[str, Any]) -> None:
        if args.receipt is None:
            return
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", dir=args.receipt.parent, delete=False
        ) as temporary:
            json.dump(
                {"schema_version": 1, "project": args.project, "submissions": values}, temporary
            )
            temporary.flush()
            os.fsync(temporary.fileno())
            name = temporary.name
        os.replace(name, args.receipt)

    statuses = reconcile(args.project, apply=args.apply, journal=journal, persist=persist)
    print(json.dumps(statuses, indent=2))
    if args.verify and any(value["state"] != "READY" for value in statuses):
        raise SystemExit("runtime indexes are not all READY; do not activate scheduling")


if __name__ == "__main__":
    main()
