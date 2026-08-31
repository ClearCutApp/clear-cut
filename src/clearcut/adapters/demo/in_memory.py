"""In-memory adapters over the CP-043 seed, wired in for `CLEARCUT_MODE=mock`
(D36).

Each class below implements one of the eight application ports directly over
`scenario.py`'s planted data -- no service behind them, no I/O, no clock, no
environment read. `LoreStore` and `TrackerStore` alone carry mutable state (an
in-process dict), because a producer's PATCH request and `EvaluateDelta`'s
carry-forward join need a store that remembers a write, not a canned
response; the other six classes echo `scenario.py`'s data back unconditionally
-- the same shape `tests/unit/fakes.py` already established for the five
read-only ports.

This package is production code for the demo image, not a test double:
`composition.py` cannot import from `tests/`, so these classes are what
`CLEARCUT_MODE=mock` actually wires (D36).

No exception class of its own: the two failure paths below (`latest` on an
unknown id, `search` on an unindexed project) raise or return the same way
the live adapters' ports already promise, using the three
`clearcut.domain.errors` types directly. CP-038's contract walk scans every
module under `adapters/` for an unclassified `Exception` subclass, so a new
name here would cost a domain-error decision this checkpoint does not need
to take.
"""

from clearcut.adapters.demo import scenario
from clearcut.application.ports import GroundedAnswer, RightsClaim
from clearcut.domain.bible import BibleFact
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.finding import Category, Finding
from clearcut.domain.jurisdiction import Jurisdiction
from clearcut.domain.script import Scene, Script
from clearcut.domain.tracker import TrackerItem


class InMemoryScriptIngestion:
    """Implements `ScriptIngestion`: always returns the planted scenes."""

    def parse(self, gcs_uri: str, script_id: str) -> list[Scene]:
        return list(scenario.SCENES)


class InMemorySceneExtractor:
    """Implements `SceneExtractor`: always returns the two planted IP findings."""

    def extract(self, scenes: list[Scene], jurisdiction: Jurisdiction) -> list[Finding]:
        return list(scenario.EXTRACTED_FINDINGS)


class InMemoryLegalGrounding:
    """Implements `LegalGrounding`: always returns the one planted grounded answer."""

    def ground(self, query: str, jurisdiction: Jurisdiction) -> GroundedAnswer:
        return scenario.GROUNDED_ANSWER


class InMemoryRightsResearch:
    """Implements `RightsResearch`: the planted claim for the asset named."""

    def find(self, asset_name: str, category: Category, jurisdiction: Jurisdiction) -> RightsClaim:
        return scenario.RIGHTS_CLAIMS_BY_ASSET[asset_name]


class InMemoryContinuityCheck:
    """Implements `ContinuityCheck`: the planted contradiction, on its one scene."""

    def check(self, scene: Scene, facts: list[BibleFact]) -> Finding | None:
        return scenario.CONTINUITY_FINDINGS_BY_SCENE.get(scene.number)


class InMemoryLoreStore:
    """Implements `LoreStore` over an in-process dict, pre-seeded for the demo
    project. `search` on any other `project_id` returns no facts -- the
    unindexed-project path CP-040's wording depends on."""

    def __init__(self) -> None:
        self._records: dict[str, list[BibleFact | Scene]] = {
            scenario.PROJECT_ID: list(scenario.BIBLE_FACTS)
        }

    def index(self, project_id: str, records: list[BibleFact | Scene]) -> None:
        self._records.setdefault(project_id, []).extend(records)

    def search(self, project_id: str, query: str, limit: int) -> list[BibleFact]:
        records = self._records.get(project_id, [])
        facts = [record for record in records if isinstance(record, BibleFact)]
        return facts[:limit]


class InMemoryTrackerStore:
    """Implements `TrackerStore` over two in-process dicts, so a transition
    written with `save` comes back from `latest` and `latest_for_project` in
    the state it was written -- the property `PATCH /api/tracker/{item_id}`
    needs. `latest_script` is pre-seeded with the demo project's planted
    version 1 (D36's fourth criterion) and empty for every other project."""

    def __init__(self) -> None:
        self._items: dict[str, TrackerItem] = {}
        self._scripts: dict[str, Script] = {scenario.PROJECT_ID: scenario.SEEDED_SCRIPT}

    def save(self, items: list[TrackerItem]) -> None:
        for item in items:
            self._items[item.item_id] = item

    def latest(self, item_id: str) -> TrackerItem:
        try:
            return self._items[item_id]
        except KeyError:
            raise RecordNotFound(f"no tracker item found for item_id={item_id!r}") from None

    def latest_for_project(self, project_id: str) -> list[TrackerItem]:
        return [item for item in self._items.values() if item.project_id == project_id]

    def record_script(self, script: Script) -> None:
        self._scripts[script.project_id] = script

    def latest_script(self, project_id: str) -> Script | None:
        return self._scripts.get(project_id)


class InMemoryNotifier:
    """Implements `Notifier`: records the call in memory instead of reaching a
    webhook, so the demo's actions beat completes rather than 502s."""

    def __init__(self) -> None:
        self.notifications: list[tuple[TrackerItem, str]] = []

    def notify(self, item: TrackerItem, reason: str) -> None:
        self.notifications.append((item, reason))
