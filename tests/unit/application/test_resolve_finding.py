"""Unit tests for `ResolveFinding` (CP-025, docs/plan/sdd.md Section 4.2).

Hand-written fakes for both ports (AGENT.md Section 5) — no `unittest.mock`,
no network, no clock read: `at` always arrives as an argument.
"""

import inspect

import pytest

from clearcut.application.ports import Notifier, TrackerStore
from clearcut.application.resolve_finding import (
    DraftEmail,
    Notify,
    ResolveFinding,
    Transition,
)
from clearcut.domain.script import Script
from clearcut.domain.tracker import TrackerItem, TrackerState

_AT = "2026-08-31T00:00:00Z"


def _item(
    item_id: str = "itm-1",
    project_id: str = "proj-1",
    version: int = 1,
    state: TrackerState = TrackerState.BLOCKED,
    contact: str = "rights@example.com",
    required_document: str = "Sync License",
) -> TrackerItem:
    return TrackerItem(
        item_id=item_id,
        project_id=project_id,
        finding_id="EVT-001",
        scene_numbers=(3,),
        state=state,
        required_document=required_document,
        contact=contact,
        litigation_posture="none on record",
        note="",
        updated_at="2026-08-30T00:00:00Z",
        version=version,
    )


class FakeTrackerStore:
    """`latest` returns the highest version seen for `item_id`; `save`
    appends every row it receives, so a test can inspect version history."""

    def __init__(self, items: list[TrackerItem] | None = None) -> None:
        self._rows: list[TrackerItem] = list(items) if items else []

    def save(self, items: list[TrackerItem]) -> None:
        self._rows.extend(items)

    def latest(self, item_id: str) -> TrackerItem:
        matches = [row for row in self._rows if row.item_id == item_id]
        if not matches:
            raise KeyError(item_id)
        return max(matches, key=lambda row: row.version)

    def latest_for_project(self, project_id: str) -> list[TrackerItem]:
        return [row for row in self._rows if row.project_id == project_id]

    def record_script(self, script: Script) -> None:
        return None

    def latest_script(self, project_id: str) -> Script | None:
        return None

    def rows_for(self, item_id: str) -> list[TrackerItem]:
        """Test helper: every stored row for `item_id`, in insertion order."""
        return [row for row in self._rows if row.item_id == item_id]


class FakeNotifier:
    """Records every `notify` call; raises `_error` if one was given."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.calls: list[tuple[TrackerItem, str]] = []

    def notify(self, item: TrackerItem, reason: str) -> None:
        self.calls.append((item, reason))
        if self._error is not None:
            raise self._error


# Each fake bound to its port by an annotated assignment (CP-012, D3),
# before any `isinstance` check in this file.
_tracker_conforms: TrackerStore = FakeTrackerStore()
_notifier_conforms: Notifier = FakeNotifier()


def test_fake_tracker_store_satisfies_the_trackerstore_port() -> None:
    assert isinstance(_tracker_conforms, TrackerStore)


def test_fake_notifier_satisfies_the_notifier_port() -> None:
    assert isinstance(_notifier_conforms, Notifier)


def test_a_transition_writes_a_new_row_and_preserves_the_old_one() -> None:
    original = _item(version=1, state=TrackerState.BLOCKED)
    tracker = FakeTrackerStore([original])
    use_case = ResolveFinding(tracker, FakeNotifier())

    use_case.execute("itm-1", Transition(TrackerState.IN_PROGRESS), _AT)

    rows = {row.version: row for row in tracker.rows_for("itm-1")}
    assert set(rows) == {1, 2}
    assert rows[1] == original
    assert rows[2].state == TrackerState.IN_PROGRESS


def test_execute_returns_the_new_version() -> None:
    tracker = FakeTrackerStore([_item(version=1)])
    use_case = ResolveFinding(tracker, FakeNotifier())

    result = use_case.execute("itm-1", Transition(TrackerState.CLEARED), _AT)

    assert result.state == TrackerState.CLEARED
    assert result.version == 2


def test_notify_action_calls_notifier_exactly_once() -> None:
    tracker = FakeTrackerStore([_item(version=1)])
    notifier = FakeNotifier()
    use_case = ResolveFinding(tracker, notifier)

    use_case.execute("itm-1", Notify("producer requested a status update"), _AT)

    assert len(notifier.calls) == 1


def test_a_transition_on_its_own_never_calls_the_notifier() -> None:
    tracker = FakeTrackerStore([_item(version=1)])
    notifier = FakeNotifier()
    use_case = ResolveFinding(tracker, notifier)

    use_case.execute("itm-1", Transition(TrackerState.IN_PROGRESS), _AT)

    assert notifier.calls == []


def test_draft_email_action_fills_the_template_from_the_items_own_data() -> None:
    tracker = FakeTrackerStore(
        [_item(version=1, contact="clearance@studio.example", required_document="Talent Release")]
    )
    use_case = ResolveFinding(tracker, FakeNotifier())

    result = use_case.execute("itm-1", DraftEmail(), _AT)

    assert result.draft_email is not None
    assert "clearance@studio.example" in result.draft_email
    assert "Talent Release" in result.draft_email
    assert result.version == 2


def test_draft_email_action_never_calls_the_notifier() -> None:
    tracker = FakeTrackerStore([_item(version=1)])
    notifier = FakeNotifier()
    use_case = ResolveFinding(tracker, notifier)

    use_case.execute("itm-1", DraftEmail(), _AT)

    assert notifier.calls == []


def test_resolve_finding_module_never_replaces_a_trackeritem_directly() -> None:
    """The versioned-row rule has one owner, `TrackerItem` (D22): this use
    case computes no version of its own and never calls `dataclasses.replace`."""
    import clearcut.application.resolve_finding as module

    source = inspect.getsource(module)
    assert "replace(" not in source
    assert ".version + 1" not in source
    assert ".version - 1" not in source


def test_an_unknown_item_id_propagates_the_stores_error_unchanged() -> None:
    """`RecordNotFound` (D23) has no owner yet (CP-034 defines it); this use
    case simply never catches anything from `tracker.latest`, so whatever the
    store raises today -- `KeyError` in this fake, `TrackerItemNotFound` in
    the real ClickHouse adapter -- propagates unchanged, satisfying CP-025's
    "propagate unchanged" criterion without anticipating CP-034's type."""
    tracker = FakeTrackerStore([])
    use_case = ResolveFinding(tracker, FakeNotifier())

    with pytest.raises(KeyError):
        use_case.execute("no-such-item", Transition(TrackerState.IN_PROGRESS), _AT)


def test_a_notifier_failure_does_not_lose_an_already_saved_transition() -> None:
    tracker = FakeTrackerStore([_item(version=1)])
    use_case = ResolveFinding(tracker, FakeNotifier())
    use_case.execute("itm-1", Transition(TrackerState.IN_PROGRESS), _AT)

    raising_notifier = ResolveFinding(tracker, FakeNotifier(error=RuntimeError("webhook down")))
    with pytest.raises(RuntimeError):
        raising_notifier.execute("itm-1", Notify("status update"), _AT)

    rows = {row.version: row for row in tracker.rows_for("itm-1")}
    assert rows[2].state == TrackerState.IN_PROGRESS


class _PositionalOnlyTrackerStore:
    """Parameter names differ from `TrackerStore`'s, so a keyword call fails."""

    def __init__(self, item: TrackerItem) -> None:
        self._item = item
        self.saved: list[list[TrackerItem]] = []

    def save(self, a: list[TrackerItem]) -> None:
        self.saved.append(a)

    def latest(self, a: str) -> TrackerItem:
        return self._item

    def latest_for_project(self, a: str) -> list[TrackerItem]:
        return []

    def record_script(self, a: Script) -> None:
        return None

    def latest_script(self, a: str) -> Script | None:
        return None


class _PositionalOnlyNotifier:
    """Parameter names differ from `Notifier`'s, so a keyword call fails."""

    def __init__(self) -> None:
        self.calls: list[tuple[TrackerItem, str]] = []

    def notify(self, a: TrackerItem, b: str) -> None:
        self.calls.append((a, b))


def test_port_methods_are_called_positionally() -> None:
    """D15: a keyword call through either fake raises `TypeError`."""
    tracker = _PositionalOnlyTrackerStore(_item(version=1))
    notifier = _PositionalOnlyNotifier()
    use_case = ResolveFinding(tracker, notifier)

    transitioned = use_case.execute("itm-1", Transition(TrackerState.IN_PROGRESS), _AT)
    use_case.execute("itm-1", Notify("status update"), _AT)

    assert transitioned.state == TrackerState.IN_PROGRESS
    assert tracker.saved == [[transitioned]]
    assert notifier.calls == [(_item(version=1), "status update")]
