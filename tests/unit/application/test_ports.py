"""Port-conformance tests for `clearcut.application.ports` (CP-005, CP-018).

Each port is a `@runtime_checkable` Protocol. `isinstance` against it checks
only that the required methods exist, so these tests prove conformance
rather than assume it: a hand-written fake missing a method must fail the
check.
"""

from clearcut.application.ports import (
    AnalysisJobStore,
    FindingStore,
    LegalGrounding,
    LoreStore,
    Notifier,
    ProjectStore,
    RightsResearch,
    SceneExtractor,
    ScriptIngestion,
    ScriptStorage,
    ScriptStore,
    TrackerStore,
)
from clearcut.domain.script import Script
from clearcut.domain.tracker import TrackerItem
from tests.unit.fakes import (
    FakeAnalysisJobStore,
    FakeFindingStore,
    FakeLegalGrounding,
    FakeLoreStore,
    FakeProjectStore,
    FakeRightsResearch,
    FakeSceneExtractor,
    FakeScriptIngestion,
    FakeScriptStorage,
    FakeScriptStore,
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
    ProjectStore: FakeProjectStore(),
    ScriptStore: FakeScriptStore(),
    FindingStore: FakeFindingStore(),
    AnalysisJobStore: FakeAnalysisJobStore(),
    ScriptStorage: FakeScriptStorage(),
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


class _ScriptStoreMissingLatest:
    """A stub implementing only three of `ScriptStore`'s four methods."""

    def save(self, script: Script) -> None:
        return None

    def get(self, project_id: str, script_id: str) -> Script:
        raise KeyError(script_id)

    def for_project(self, project_id: str) -> list[Script]:
        return []


def test_a_scriptstore_stub_missing_one_required_method_fails_isinstance() -> None:
    assert not isinstance(_ScriptStoreMissingLatest(), ScriptStore)
