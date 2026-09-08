"""Human review is pinned to the immutable binding and transactional generation."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from clearcut.application.analysis_documents import tracker_data
from clearcut.application.reconfirm_clearance import ReconfirmClearance
from clearcut.domain.durable_analysis import ClearanceSnapshot
from clearcut.domain.screenplay import ContentReference
from clearcut.domain.tracker import (
    ClearanceDetails,
    InvalidClearance,
    TrackerConflict,
    TrackerState,
)
from tests.unit.adapters.test_clearance_transactions import item, store
from tests.unit.application.test_analysis_checkpoints import Artifacts


@pytest.mark.parametrize("race", ["none", "generation", "item", "removed", "revision", "locations"])
def test_only_explicit_confirmation_of_current_applicability_clears_review(race):
    client, tracker = store()
    source = replace(item(), state=TrackerState.CLEARED, needs_review=True)
    client.data["project_access/project"]["active_generation"] = "generation"
    base = "project_access/project/clearance_generations/generation/items/asset"
    client.data[base] = tracker_data(source)
    artifacts = Artifacts()
    reference = ContentReference("manifest", "hash", 1)
    artifacts.values["manifest"] = {
        "project_id": "project",
        "revision_id": "revision-2",
        "clearance_bindings": {
            "asset": {
                "revision_id": "revision-2",
                "signature": "applicable-content",
                "present": race != "removed",
            }
        },
    }

    def snapshot(project_id):
        if race == "locations":
            client.data["project_access/project"]["production_context_json"] = '{"locations":[]}'
        if race == "generation":
            client.data["project_access/project"]["active_generation"] = "next"
        if race == "item":
            client.data[base] = tracker_data(
                replace(source, version=2, clearance_conditions="Changed permission scope")
            )
        return ClearanceSnapshot("generation", 1, reference), [source]

    use_case = ReconfirmClearance(SimpleNamespace(snapshot=snapshot), artifacts, tracker)
    revision = "revision-old" if race == "revision" else "revision-2"
    if race != "none":
        with pytest.raises(
            TrackerConflict if race in {"generation", "item", "locations"} else InvalidClearance
        ):
            use_case.execute("project", "asset", 1, revision, "producer", "later")
        assert base + "/events/2" not in client.data
    else:
        confirmed = use_case.execute("project", "asset", 1, revision, "producer", "later")
        assert confirmed.state is TrackerState.CLEARED and not confirmed.needs_review
        event = client.data[base + "/events/2"]
        assert event["revision_id"] == "revision-2" and event["actor"] == "producer"
        assert event["action"] == "clearance_reconfirmed"
        assert client.data[base] == tracker_data(source)


def test_changing_permission_scope_requires_another_review_but_editing_a_note_does_not():
    source = replace(item(), state=TrackerState.CLEARED, clearance_conditions="Argentina")
    details = ClearanceDetails("Updated note", "Argentina", "", "", (), None)
    assert not source.with_details(details, "later").needs_review
    assert source.with_details(
        replace(details, clearance_conditions="Worldwide"), "later"
    ).needs_review
    assert source.with_details(
        replace(details, evidence_file_ids=("new-proof",)), "later"
    ).needs_review
    assert (
        replace(source, needs_review=True)
        .transitioned_to(TrackerState.CLEARED, "later")
        .needs_review
    )
