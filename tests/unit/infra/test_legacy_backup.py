from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from infra.backup_legacy_state import backup, verify_source
from infra.migration_snapshot import TABLE_KEYS, canonical, verify


def fixture() -> dict[str, list[dict[str, Any]]]:
    return {
        "projects": [
            {
                "project_id": "project",
                "title": "Película",
                "jurisdiction_code": "AR",
                "created_at": "now",
            }
        ],
        "script_versions": [
            {
                "project_id": "project",
                "script_id": "script",
                "version": 3,
                "gcs_uri": "gs://intake/original.pdf",
                "jurisdiction_code": "AR",
                "scenes": '[{"text":"Diálogo español"}]',
            }
        ],
        "findings": [
            {
                "project_id": "project",
                "script_id": "script",
                "finding_id": "finding",
                "raw_text": "Marca",
            }
        ],
        "tracker_items": [
            {
                "project_id": "project",
                "item_id": "item",
                "version": 1,
                "finding_id": "finding",
                "state": "CLEARED",
                "draft_email": None,
            }
        ],
        "analysis_jobs": [
            {
                "project_id": "project",
                "analysis_id": "analysis",
                "version": 1,
                "script_id": "script",
                "state": "SUCCEEDED",
                "created_at": datetime(2026, 9, 6, 12, 0, 0, 123000, tzinfo=UTC),
            }
        ],
    }


class Client:
    def __init__(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self.data = data
        self.queries: list[tuple[str, dict[str, Any]]] = []
        self.fail_table: str | None = None

    def query_rows_stream(self, query: str, **kwargs: Any) -> Any:
        table = query.split()[3]
        self.queries.append((query, kwargs))
        if table == self.fail_table:
            raise RuntimeError("source interrupted")
        values = self.data[table]
        columns = list(values[0]) if values else list(TABLE_KEYS[table])

        class Stream:
            source = SimpleNamespace(column_names=columns)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def __iter__(self):
                return iter([tuple(row[column] for column in columns) for row in values])

        return Stream()


def test_raw_backup_preserves_duplicates_unicode_nulls_utc_and_original_ids(tmp_path):
    data = fixture()
    data["tracker_items"].append(deepcopy(data["tracker_items"][0]))
    client = Client(data)
    report = backup(client, tmp_path, ["project"], "source-hash")
    assert report["status"] == "records_reconciled" and report["publication_allowed"] is False
    assert report["raw_rows"]["tracker_items"] == 2 and report["logical_rows"]["tracker_items"] == 1
    assert report["maximum_script_version"] == {"project": 3}
    assert report["legacy_audit_history_complete"] is False
    assert "Diálogo español" in (tmp_path / "script_versions.jsonl").read_text()
    assert '"draft_email":null' in (tmp_path / "tracker_items.jsonl").read_text()
    assert "2026-09-06T12:00:00.123000+00:00" in (tmp_path / "analysis_jobs.jsonl").read_text()
    assert all(
        "FINAL" not in query
        and "project"
        not in query.replace("project_id", "").replace("project_ids", "").replace("projects", "")
        for query, _ in client.queries
    )
    assert all(
        options["parameters"] == {"project_ids": ["project"]} and options["tz_mode"] == "aware"
        for _, options in client.queries
    )


def test_resume_keeps_completed_tables_and_rejects_changed_backup_or_source_identity(tmp_path):
    client = Client(fixture())
    client.fail_table = "findings"
    with pytest.raises(RuntimeError):
        backup(client, tmp_path, ["project"], "source")
    captured = (tmp_path / "projects.jsonl").read_bytes()
    client.fail_table = None
    client.queries.clear()
    backup(client, tmp_path, ["project"], "source")
    assert len(client.queries) == 3 and (tmp_path / "projects.jsonl").read_bytes() == captured
    with pytest.raises(ValueError):
        backup(client, tmp_path, ["project"], "other-source")
    (tmp_path / "projects.jsonl").write_text("changed")
    with pytest.raises(ValueError):
        backup(client, tmp_path, ["project"], "source")


def test_crash_after_table_rename_before_receipt_is_reconciled_without_overwrite(tmp_path):
    import json

    client = Client(fixture())
    backup(client, tmp_path, ["project"], "source")
    path = tmp_path / "manifest.json"
    value = json.loads(path.read_bytes())
    value["tables"].pop("projects")
    path.write_bytes(canonical(value))
    original = (tmp_path / "projects.jsonl").read_bytes()
    client.queries.clear()
    backup(client, tmp_path, ["project"], "source")
    assert len(client.queries) == 1 and (tmp_path / "projects.jsonl").read_bytes() == original


@pytest.mark.parametrize(
    "problem", ["conflicting-version", "global-job-collision", "missing-link", "ambiguous-latest"]
)
def test_conflicts_and_missing_links_block_migration_without_renaming_records(tmp_path, problem):
    data = fixture()
    scope = ["project"]
    if problem == "conflicting-version":
        data["tracker_items"].append({**data["tracker_items"][0], "state": "BLOCKED"})
    if problem == "missing-link":
        data["findings"][0]["script_id"] = "missing"
    if problem == "ambiguous-latest":
        data["script_versions"].append({**data["script_versions"][0], "script_id": "another"})
    if problem == "global-job-collision":
        scope.append("other")
        data["projects"].append({**data["projects"][0], "project_id": "other"})
        data["script_versions"].append({**data["script_versions"][0], "project_id": "other"})
        data["analysis_jobs"].append({**data["analysis_jobs"][0], "project_id": "other"})
    report = backup(Client(data), tmp_path, scope, "source")
    assert report["status"] == "blocked" and report["issues"]
    assert report["publication_allowed"] is False
    assert "item" in (tmp_path / "tracker_items.jsonl").read_text()


def test_recheck_detects_source_changes_and_incomplete_jobs_never_relaunch(tmp_path):
    data = fixture()
    data["analysis_jobs"].append(
        {
            **data["analysis_jobs"][0],
            "analysis_id": "interrupted",
            "script_id": "not-written",
            "state": "RUNNING",
        }
    )
    client = Client(data)
    report = backup(client, tmp_path, ["project"], "source")
    assert report["status"] == "records_reconciled"
    assert report["incomplete_jobs_preserved_without_relaunch"][0]["analysis_id"] == "interrupted"
    assert verify_source(client, tmp_path, "source")["source_unchanged_at_recheck"] is True
    data["projects"][0]["title"] = "Later title"
    changed = verify_source(client, tmp_path, "source")
    assert (
        changed["source_changed_tables"] == ["projects"] and changed["publication_allowed"] is False
    )


def test_foreign_project_rows_are_not_backed_up_and_invalid_local_paths_are_rejected(tmp_path):
    import json

    data = fixture()
    data["projects"][0]["project_id"] = "foreign"
    with pytest.raises(ValueError):
        backup(Client(data), tmp_path, ["project"], "source")
    assert not (tmp_path / "projects.jsonl").exists()
    complete = tmp_path / "complete"
    backup(Client(fixture()), complete, ["project"], "source")
    manifest_path = complete / "manifest.json"
    value = json.loads(manifest_path.read_bytes())
    value["tables"]["projects"]["file"] = "../private"
    manifest_path.write_bytes(canonical(value))
    with pytest.raises(ValueError):
        verify(complete)
