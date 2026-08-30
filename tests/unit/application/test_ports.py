"""Port-conformance tests for `clearcut.application.ports` (CP-005, CP-018).

Each port is a `@runtime_checkable` Protocol. `isinstance` against it checks
only that the required methods exist, so these tests prove conformance
rather than assume it: a hand-written fake missing a method must fail the
check.
"""

from clearcut.application.ports import (
    LegalGrounding,
    LoreStore,
    Notifier,
    RightsResearch,
    SceneExtractor,
    ScriptIngestion,
    TrackerStore,
)
from clearcut.domain.script import Script
from clearcut.domain.tracker import TrackerItem
from tests.unit.fakes import (
    FakeLegalGrounding,
    FakeLoreStore,
    FakeRightsResearch,
    FakeSceneExtractor,
    FakeScriptIngestion,
)


class FakeTrackerStore:
    """A hand-written `TrackerStore`, for conformance only — no real adapter yet."""

    def save(self, items: list[TrackerItem]) -> None:
        return None

    def latest(self, item_id: str) -> TrackerItem:
        raise KeyError(item_id)

    def latest_for_project(self, project_id: str) -> list[TrackerItem]:
        return []

    def record_script(self, script: Script) -> None:
        return None

    def latest_script(self, project_id: str) -> Script | None:
        return None


class FakeNotifier:
    """A hand-written `Notifier`, for conformance only — no real adapter yet."""

    def notify(self, item: TrackerItem, reason: str) -> None:
        return None


# Bound to their ports by an annotated assignment (CP-012, D3): `isinstance`
# above proves the required methods exist, but not their parameter names,
# order, or types — mypy checks this assignment structurally, so a signature
# drift here fails at type-check time rather than passing silently.
_store: TrackerStore = FakeTrackerStore()
_notifier: Notifier = FakeNotifier()


_FAKES_BY_PORT = {
    ScriptIngestion: FakeScriptIngestion(),
    SceneExtractor: FakeSceneExtractor(),
    LegalGrounding: FakeLegalGrounding(),
    RightsResearch: FakeRightsResearch(),
    LoreStore: FakeLoreStore(),
    TrackerStore: FakeTrackerStore(),
    Notifier: FakeNotifier(),
}


def test_fakes_satisfy_their_ports() -> None:
    for port, fake in _FAKES_BY_PORT.items():
        assert isinstance(fake, port), f"{fake!r} does not satisfy {port.__name__}"


class _LoreStoreMissingSearch:
    """A stub implementing only half of `LoreStore`, to prove the check bites."""

    def index(self, project_id: str, records: list[object]) -> None:
        return None


def test_a_stub_missing_one_required_method_fails_isinstance() -> None:
    assert not isinstance(_LoreStoreMissingSearch(), LoreStore)


class _TrackerStoreMissingLatest:
    """A stub implementing only four of `TrackerStore`'s five methods."""

    def save(self, items: list[TrackerItem]) -> None:
        return None

    def latest_for_project(self, project_id: str) -> list[TrackerItem]:
        return []

    def record_script(self, script: Script) -> None:
        return None

    def latest_script(self, project_id: str) -> Script | None:
        return None


def test_a_trackerstore_stub_missing_one_required_method_fails_isinstance() -> None:
    assert not isinstance(_TrackerStoreMissingLatest(), TrackerStore)
