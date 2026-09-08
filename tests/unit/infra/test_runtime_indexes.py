from copy import deepcopy
from typing import Any
from unittest.mock import Mock

import pytest
from infra.provision_runtime_indexes import INDEXES, create_command, inspect, reconcile


def inventory(state: str = "READY") -> list[dict[str, Any]]:
    return [
        {
            "name": f"projects/project-id/databases/(default)/collectionGroups/"
            f"{collection}/indexes/{field}",
            "queryScope": "COLLECTION",
            "state": state,
            "fields": [
                {"fieldPath": "state", "order": "ASCENDING"},
                {"fieldPath": field, "order": "ASCENDING"},
                {"fieldPath": "__name__", "order": "ASCENDING"},
            ],
        }
        for collection, field in INDEXES
    ]


def test_runtime_indexes_cover_all_four_fenced_queues_and_existing_ready_is_noop():
    run = Mock(return_value=inventory())
    result = reconcile("project-id", apply=True, run=run)
    assert len(result) == 8 and all(value["state"] == "READY" for value in result)
    assert run.call_count == 1 and "list" in run.call_args.args[0]


def test_only_missing_index_is_created_and_submission_is_not_verification():
    values = inventory()
    run = Mock(side_effect=[values[:-1], {"name": "operations/create-index"}])
    result = reconcile("project-id", apply=True, run=run)
    assert run.call_count == 2 and "create" in run.call_args.args[0]
    assert result[-1]["state"] == "SUBMITTED_UNVERIFIED"
    assert "--async" in run.call_args.args[0]
    assert not any("delete" in argument for argument in run.call_args.args[0])


def test_wrong_scope_or_field_order_does_not_count_as_required_index():
    values = inventory()
    changed = deepcopy(values)
    changed[0]["queryScope"] = "COLLECTION_GROUP"
    changed[1]["fields"].reverse()
    found = inspect("project-id", Mock(return_value=changed))
    assert len(found) == 6
    command = create_command("project-id", "analysis_jobs", "available_at")
    assert command[command.index("--query-scope") + 1] == "collection"


def test_building_index_is_never_recreated_and_failed_index_stops_mutations():
    run = Mock(return_value=inventory("CREATING"))
    assert all(
        value["state"] == "CREATING" for value in reconcile("project-id", apply=True, run=run)
    )
    assert run.call_count == 1
    run = Mock(return_value=inventory("NEEDS_REPAIR"))
    with pytest.raises(RuntimeError):
        reconcile("project-id", apply=True, run=run)
    assert run.call_count == 1


def test_unknown_create_is_journaled_before_call_and_not_blindly_resubmitted():
    journal: dict[str, Any] = {}
    persisted: list[dict[str, Any]] = []

    def run(arguments):
        if "list" in arguments:
            return inventory()[:-1]
        assert (
            persisted
            and persisted[-1]["notification_outbox/lease_until"]["state"] == "submission_unknown"
        )
        raise RuntimeError("response lost")

    with pytest.raises(RuntimeError):
        reconcile(
            "project-id",
            apply=True,
            run=run,
            journal=journal,
            persist=lambda value: persisted.append(deepcopy(value)),
        )
    retry = Mock(return_value=inventory()[:-1])
    result = reconcile("project-id", apply=True, run=retry, journal=journal)
    assert retry.call_count == 1 and result[-1]["state"] == "SUBMISSION_UNRESOLVED"
