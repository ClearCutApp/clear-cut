"""Tests for TrackerItem and TrackerState (docs/plan/sdd.md Section 2)."""

import dataclasses

import pytest

from clearcut.domain.tracker import (
    EMPTY_CLEARANCE_SUMMARY,
    ClearanceRollup,
    ClearanceSummary,
    TrackerItem,
    TrackerState,
    clearance_rollup,
    clearance_summary,
)


def _item(
    state: TrackerState = TrackerState.BLOCKED,
    version: int = 1,
    project_id: str = "proj-1",
    needs_review: bool = False,
) -> TrackerItem:
    return TrackerItem(
        item_id="itm-1",
        project_id=project_id,
        finding_id="EVT-001",
        scene_numbers=(3,),
        state=state,
        required_document="Sync License",
        contact="rights@example.com",
        litigation_posture="none on record",
        note="",
        updated_at="2026-08-30T00:00:00Z",
        version=version,
        needs_review=needs_review,
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


def test_transitioned_to_carries_project_id_unchanged():
    original = _item(project_id="proj-a")
    updated = original.transitioned_to(TrackerState.IN_PROGRESS, at="2026-08-31T00:00:00Z")

    assert updated.project_id == original.project_id


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


def test_flagged_for_review_carries_project_id_unchanged():
    original = _item(project_id="proj-a")
    updated = original.flagged_for_review(at="2026-08-31T00:00:00Z")

    assert updated.project_id == original.project_id


def test_with_draft_email_sets_the_draft_and_bumps_version():
    original = _item(version=1)
    updated = original.with_draft_email("Dear rights holder...", at="2026-08-31T00:00:00Z")

    assert updated.draft_email == "Dear rights holder..."
    assert updated.version == 2
    assert updated.updated_at == "2026-08-31T00:00:00Z"


def test_with_draft_email_leaves_state_unchanged():
    original = _item(state=TrackerState.CLEARED, version=1)
    updated = original.with_draft_email("Dear rights holder...", at="2026-08-31T00:00:00Z")
    assert updated.state == TrackerState.CLEARED


def test_with_draft_email_leaves_the_receiver_unchanged():
    original = _item(version=1)
    original.with_draft_email("Dear rights holder...", at="2026-08-31T00:00:00Z")

    assert original.draft_email is None
    assert original.version == 1


def test_with_draft_email_carries_project_id_unchanged():
    original = _item(project_id="proj-a")
    updated = original.with_draft_email("Dear rights holder...", at="2026-08-31T00:00:00Z")

    assert updated.project_id == original.project_id


@pytest.mark.parametrize("blank_draft", ["", "   "])
def test_with_draft_email_rejects_a_blank_or_whitespace_only_draft(blank_draft):
    original = _item(version=1)
    with pytest.raises(ValueError):
        original.with_draft_email(blank_draft, at="2026-08-31T00:00:00Z")


def test_noted_sets_the_note_and_bumps_version():
    original = _item(version=1)
    updated = original.noted("scene 7 removed in version 2", at="2026-08-31T00:00:00Z")

    assert updated.note == "scene 7 removed in version 2"
    assert updated.version == 2
    assert updated.updated_at == "2026-08-31T00:00:00Z"


def test_noted_leaves_state_unchanged():
    original = _item(state=TrackerState.CLEARED, version=1)
    updated = original.noted("scene 7 removed in version 2", at="2026-08-31T00:00:00Z")
    assert updated.state == TrackerState.CLEARED


def test_noted_leaves_the_receiver_unchanged():
    original = _item(version=1)
    original.noted("scene 7 removed in version 2", at="2026-08-31T00:00:00Z")

    assert original.note == ""
    assert original.version == 1


def test_noted_carries_project_id_unchanged():
    original = _item(project_id="proj-a")
    updated = original.noted("scene 7 removed in version 2", at="2026-08-31T00:00:00Z")

    assert updated.project_id == original.project_id


@pytest.mark.parametrize("blank_note", ["", "   "])
def test_noted_rejects_a_blank_or_whitespace_only_note(blank_note):
    original = _item(version=1)
    with pytest.raises(ValueError):
        original.noted(blank_note, at="2026-08-31T00:00:00Z")


def test_flagged_and_noted_sets_note_and_needs_review_at_one_version_bump():
    original = _item(state=TrackerState.CLEARED, version=3)
    updated = original.flagged_and_noted("cleared against scene 2", at="2026-08-31T00:00:00Z")

    assert updated.needs_review is True
    assert updated.note == "cleared against scene 2"
    assert updated.state == TrackerState.CLEARED
    assert updated.version == 4
    assert updated.updated_at == "2026-08-31T00:00:00Z"


def test_flagged_and_noted_leaves_the_receiver_unchanged():
    original = _item(version=1)
    original.flagged_and_noted("cleared against scene 2", at="2026-08-31T00:00:00Z")

    assert original.needs_review is False
    assert original.note == ""
    assert original.version == 1


def test_flagged_and_noted_carries_project_id_unchanged():
    original = _item(project_id="proj-a")
    updated = original.flagged_and_noted("cleared against scene 2", at="2026-08-31T00:00:00Z")

    assert updated.project_id == original.project_id


def test_rejects_a_version_below_one():
    with pytest.raises(ValueError):
        TrackerItem(
            item_id="itm-1",
            project_id="proj-1",
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
            project_id="proj-1",
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


@pytest.mark.parametrize("blank_project_id", ["", "   "])
def test_rejects_a_blank_or_whitespace_only_project_id(blank_project_id):
    with pytest.raises(ValueError):
        TrackerItem(
            item_id="itm-1",
            project_id=blank_project_id,
            finding_id="EVT-001",
            scene_numbers=(1,),
            state=TrackerState.BLOCKED,
            required_document="Sync License",
            contact="rights@example.com",
            litigation_posture="none on record",
            note="",
            updated_at="2026-08-30T00:00:00Z",
            version=1,
        )


def test_clearance_rollup_of_no_items_is_all_zero_and_zero_percent():
    rollup = clearance_rollup([])

    assert rollup == ClearanceRollup(blocked=0, in_progress=0, cleared=0, needs_review=0)
    assert rollup.total == 0
    assert rollup.clearance_percent == 0


def test_clearance_rollup_counts_sum_to_total():
    items = [
        _item(state=TrackerState.BLOCKED),
        _item(state=TrackerState.IN_PROGRESS),
        _item(state=TrackerState.CLEARED),
    ]

    rollup = clearance_rollup(items)
    bucket_sum = rollup.blocked + rollup.in_progress + rollup.cleared + rollup.needs_review

    assert bucket_sum == rollup.total
    assert rollup.total == 3


def test_clearance_rollup_of_all_blocked_is_zero_percent():
    items = [_item(state=TrackerState.BLOCKED), _item(state=TrackerState.BLOCKED)]

    assert clearance_rollup(items).clearance_percent == 0


def test_clearance_rollup_of_all_cleared_is_a_hundred_percent():
    items = [_item(state=TrackerState.CLEARED), _item(state=TrackerState.CLEARED)]

    assert clearance_rollup(items).clearance_percent == 100


def test_clearance_rollup_of_one_item_in_each_of_the_four_states_is_fifty_percent():
    items = [
        _item(state=TrackerState.BLOCKED),
        _item(state=TrackerState.IN_PROGRESS),
        _item(state=TrackerState.CLEARED),
        _item(state=TrackerState.BLOCKED, needs_review=True),
    ]

    rollup = clearance_rollup(items)

    assert rollup == ClearanceRollup(blocked=1, in_progress=1, cleared=1, needs_review=1)
    assert rollup.clearance_percent == 50


def test_clearance_rollup_of_blocked_and_in_progress_is_twenty_five_percent():
    items = [_item(state=TrackerState.BLOCKED), _item(state=TrackerState.IN_PROGRESS)]

    assert clearance_rollup(items).clearance_percent == 25


def test_clearance_rollup_needs_review_takes_priority_over_state():
    items = [_item(state=TrackerState.CLEARED, needs_review=True)]

    rollup = clearance_rollup(items)

    assert rollup == ClearanceRollup(blocked=0, in_progress=0, cleared=0, needs_review=1)


def test_clearance_rollup_halved_percentage_rounds_up_and_is_an_int():
    items = [
        _item(state=TrackerState.IN_PROGRESS, needs_review=True),
        _item(state=TrackerState.BLOCKED),
        _item(state=TrackerState.BLOCKED),
        _item(state=TrackerState.BLOCKED),
    ]

    rollup = clearance_rollup(items)

    assert rollup.clearance_percent == 13
    assert isinstance(rollup.clearance_percent, int)


def test_clearance_summary_of_no_items_is_the_empty_one():
    """A project nobody has analysed answers zeroes, not an absence: the row
    still draws, with an empty bar."""
    assert clearance_summary([]) == EMPTY_CLEARANCE_SUMMARY
    assert EMPTY_CLEARANCE_SUMMARY == ClearanceSummary(
        total=0, cleared=0, in_progress=0, blocked=0, needs_review=0
    )


def test_clearance_summary_buckets_sum_to_total():
    """The four buckets partition the items -- an item is in exactly one, so
    "12 Cleared / 4 Pending / 2 Flagged" never adds up to more than the bar."""
    items = [
        _item(state=TrackerState.BLOCKED),
        _item(state=TrackerState.IN_PROGRESS),
        _item(state=TrackerState.CLEARED),
        _item(state=TrackerState.CLEARED, needs_review=True),
    ]

    summary = clearance_summary(items)

    assert summary == ClearanceSummary(total=4, cleared=1, in_progress=1, blocked=1, needs_review=1)
    assert summary.cleared + summary.in_progress + summary.blocked + summary.needs_review == 4


def test_clearance_summary_counts_a_flagged_item_once_and_not_in_its_state():
    """The rule the tracker page already applies: `needs_review` wins over
    `state`, so a cleared-but-flagged item is not also counted as cleared."""
    summary = clearance_summary([_item(state=TrackerState.CLEARED, needs_review=True)])

    assert summary == ClearanceSummary(total=1, cleared=0, in_progress=0, blocked=0, needs_review=1)


def test_clearance_summary_agrees_with_the_rollup_it_delegates_to():
    """One counting rule, two shapes. The summary carries no percentage of its
    own precisely so it cannot drift from the rollup's."""
    items = [
        _item(state=TrackerState.BLOCKED),
        _item(state=TrackerState.IN_PROGRESS),
        _item(state=TrackerState.CLEARED),
        _item(state=TrackerState.IN_PROGRESS, needs_review=True),
    ]

    summary, rollup = clearance_summary(items), clearance_rollup(items)

    assert (summary.blocked, summary.in_progress, summary.cleared, summary.needs_review) == (
        rollup.blocked,
        rollup.in_progress,
        rollup.cleared,
        rollup.needs_review,
    )
    assert summary.total == rollup.total


def test_clearance_summary_reads_any_iterable_once():
    """The port hands it `dict.values()`; a generator must work the same, so
    the function may not consume its argument twice."""
    items = (_item(state=state) for state in (TrackerState.CLEARED, TrackerState.CLEARED))

    assert clearance_summary(items) == ClearanceSummary(
        total=2, cleared=2, in_progress=0, blocked=0, needs_review=0
    )
