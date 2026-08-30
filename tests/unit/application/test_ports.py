"""Port-conformance tests for `clearcut.application.ports` (CP-005).

Each port is a `@runtime_checkable` Protocol. `isinstance` against it checks
only that the required methods exist, so these tests prove conformance
rather than assume it: a hand-written fake missing a method must fail the
check.
"""

from clearcut.application.ports import (
    LegalGrounding,
    LoreStore,
    RightsResearch,
    SceneExtractor,
    ScriptIngestion,
)
from tests.unit.fakes import (
    FakeLegalGrounding,
    FakeLoreStore,
    FakeRightsResearch,
    FakeSceneExtractor,
    FakeScriptIngestion,
)

_FAKES_BY_PORT = {
    ScriptIngestion: FakeScriptIngestion(),
    SceneExtractor: FakeSceneExtractor(),
    LegalGrounding: FakeLegalGrounding(),
    RightsResearch: FakeRightsResearch(),
    LoreStore: FakeLoreStore(),
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
