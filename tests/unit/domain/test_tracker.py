"""Tests for TrackerItem and TrackerState (docs/plan/sdd.md Section 2)."""

import dataclasses

import pytest

from clearcut.domain.tracker import TrackerItem, TrackerState


def _item(state: TrackerState = TrackerState.BLOCKED, version: int = 1) -> TrackerItem:
    return TrackerItem(
        item_id="itm-1",
        finding_id="EVT-001",
        scene_numbers=(3,),
        state=state,
        required_document="Sync License",
        contact="rights@example.com",
        litigation_posture="none on record",
        note="",
        updated_at="2026-08-30T00:00:00Z",
        version=version,
    )


def test_defaults_needs_review_to_false():
    item = _item()
    assert item.needs_review is False


def test_draft_email_defaults_to_none():
    item = _item()
    assert item.draft_email is None


def test_transitioned_to_returns_a_new_item_at_the_next_version():
    original = _item(state=TrackerState.BLOCKED, version=1)
    updated = original.transitioned_to(TrackerState.IN_PROGRESS, at="2026-08-31T00:00:00Z")

    assert updated.state == TrackerState.IN_PROGRESS
    assert updated.version == 2
    assert updated.updated_at == "2026-08-31T00:00:00Z"


def test_transitioned_to_leaves_the_receiver_unchanged():
    original = _item(state=TrackerState.BLOCKED, version=1)
    original.transitioned_to(TrackerState.IN_PROGRESS, at="2026-08-31T00:00:00Z")

    assert original.state == TrackerState.BLOCKED
    assert original.version == 1


def test_tracker_item_is_frozen():
    item = _item()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(item, "state", TrackerState.CLEARED)


@pytest.mark.parametrize(
    "from_state",
    [TrackerState.BLOCKED, TrackerState.IN_PROGRESS, TrackerState.CLEARED],
)
@pytest.mark.parametrize(
    "to_state",
    [TrackerState.BLOCKED, TrackerState.IN_PROGRESS, TrackerState.CLEARED],
)
def test_every_ordered_pair_of_states_is_a_legal_transition(from_state, to_state):
    original = _item(state=from_state, version=1)
    updated = original.transitioned_to(to_state, at="2026-08-31T00:00:00Z")
    assert updated.state == to_state


def test_transitioning_to_the_current_state_still_bumps_the_version():
    original = _item(state=TrackerState.CLEARED, version=4)
    updated = original.transitioned_to(TrackerState.CLEARED, at="2026-08-31T00:00:00Z")

    assert updated.state == TrackerState.CLEARED
    assert updated.version == 5


def test_flagged_for_review_sets_needs_review_and_bumps_version():
    original = _item(version=1)
    updated = original.flagged_for_review(at="2026-08-31T00:00:00Z")

    assert updated.needs_review is True
    assert updated.version == 2
    assert updated.updated_at == "2026-08-31T00:00:00Z"


def test_flagged_for_review_leaves_state_unchanged():
    original = _item(state=TrackerState.CLEARED, version=1)
    updated = original.flagged_for_review(at="2026-08-31T00:00:00Z")
    assert updated.state == TrackerState.CLEARED


def test_flagged_for_review_leaves_the_receiver_unchanged():
    original = _item(version=1)
    original.flagged_for_review(at="2026-08-31T00:00:00Z")

    assert original.needs_review is False
    assert original.version == 1


def test_rejects_a_version_below_one():
    with pytest.raises(ValueError):
        TrackerItem(
            item_id="itm-1",
            finding_id="EVT-001",
            scene_numbers=(1,),
            state=TrackerState.BLOCKED,
            required_document="Sync License",
            contact="rights@example.com",
            litigation_posture="none on record",
            note="",
            updated_at="2026-08-30T00:00:00Z",
            version=0,
        )


def test_rejects_empty_scene_numbers():
    with pytest.raises(ValueError):
        TrackerItem(
            item_id="itm-1",
            finding_id="EVT-001",
            scene_numbers=(),
            state=TrackerState.BLOCKED,
            required_document="Sync License",
            contact="rights@example.com",
            litigation_posture="none on record",
            note="",
            updated_at="2026-08-30T00:00:00Z",
            version=1,
        )
