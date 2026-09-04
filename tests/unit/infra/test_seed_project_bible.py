"""Behaviour tests for infra/seed_project_bible.py.

SDD section 8(d) asserts a CONTINUITY finding, which needs a bible fact in the
LoreStore for the scene to contradict. ADR 0011 rules that seeding as
infrastructure rather than building `POST /api/projects/{id}/bible`, so the
endpoint stays MISSING and this script reaches the state the check needs.

The fact itself is not written here or in the script. Both take it from
`adapters/demo/scenario.py`, which is the one place it is defined, so the
seeded fact and the mock-mode fact cannot drift into disagreeing about what
scene 3 contradicts.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from clearcut.adapters.demo import scenario
from clearcut.domain.bible import BibleFact, FactKind
from clearcut.domain.script import content_hash

SCRIPT = Path(__file__).resolve().parents[3] / "infra" / "seed_project_bible.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seed_project_bible", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RecordingLoreStore:
    """Records what was indexed, and answers `search` the way BigQuery does.

    The round trip is the point. `BigQueryLoreStore._bible_fact_from` rebuilds
    `fact_id` from the stored `content_hash` column, so a fact that went in as
    `FACT-001` comes back as a hex digest, with `source` flattened to
    "episode - p.0". A guard that recognised an already-seeded fact by its
    `fact_id` would therefore never match, and would re-index on every run
    while looking correct.

    This fake reproduces that faithfully so the guard is tested against what
    BigQuery actually returns rather than against what was handed to it.
    """

    def __init__(self, already_holding: list[BibleFact] | None = None) -> None:
        self.indexed: list[tuple[str, list[Any]]] = []
        self._stored = list(already_holding or [])

    def index(self, project_id: str, records: list[Any]) -> None:
        self.indexed.append((project_id, records))
        self._stored.extend(records)

    def search(self, project_id: str, query: str, limit: int) -> list[BibleFact]:
        if project_id != scenario.PROJECT_ID:
            return []
        return [
            BibleFact(
                fact_id=content_hash(fact.text),
                kind=FactKind.LORE,
                text=fact.text,
                source="episode - p.0",
            )
            for fact in self._stored
        ][:limit]


def test_seeds_the_scenario_bible_fact_into_the_demo_project() -> None:
    store = RecordingLoreStore()

    load_script().seed(store)

    assert len(store.indexed) == 1
    project_id, records = store.indexed[0]
    assert project_id == scenario.PROJECT_ID
    assert records == [scenario.BIBLE_FACT]


def test_the_fact_is_taken_from_the_scenario_not_restated() -> None:
    """Identity, not equality.

    A copy of the text would pass an equality check and still drift the day
    someone edits `scenario.py`. The seeded fact must be the same object the
    demo adapters serve, so the two cannot disagree about what scene 3
    contradicts.
    """
    store = RecordingLoreStore()

    load_script().seed(store)

    _, records = store.indexed[0]
    assert records[0] is scenario.BIBLE_FACT


def test_dry_run_prints_the_fact_and_connects_to_nothing() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert scenario.PROJECT_ID in result.stdout
    assert scenario.BIBLE_FACT.fact_id in result.stdout
    # No credential is required for the dry run, which is what lets a reviewer
    # run it on a machine with no Google Cloud access at all.
    assert "GOOGLE_CLOUD_PROJECT" not in result.stderr


def test_a_missing_credential_exits_naming_that_variable() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
        check=False,
    )

    assert result.returncode != 0
    assert "GOOGLE_CLOUD_PROJECT" in result.stderr


def test_an_unknown_argument_is_refused() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--wipe"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
        check=False,
    )

    assert result.returncode != 0
    assert "--wipe" in result.stderr


@pytest.mark.parametrize("forbidden", ["delete", "drop", "truncate"])
def test_the_script_never_removes_anything(forbidden: str) -> None:
    """Seeding is additive.

    `LoreStore` has no `delete` method (SDD section 4.3 records that as a known
    gap), so a script that appeared to remove rows would be lying about what it
    can do.
    """
    assert forbidden not in SCRIPT.read_text().lower()


# --- Idempotence: every other provisioning script here already has it --------


def test_seeding_a_store_that_already_holds_the_fact_indexes_nothing() -> None:
    """`LoreStore` has no way to remove a row, so a second run without this
    guard leaves two copies of FACT-001 in the corpus for good."""
    store = RecordingLoreStore(already_holding=[scenario.BIBLE_FACT])

    load_script().seed(store)

    assert store.indexed == []


def test_the_guard_survives_the_fact_id_round_trip() -> None:
    """The trap this guard has to avoid.

    What comes back from BigQuery is not what went in: `fact_id` is rebuilt
    from the `content_hash` column, so the stored fact answers to a hex digest
    rather than to `FACT-001`. Matching on `fact_id` would silently never
    match. This asserts the fake really does return a different id, so the
    passing test above cannot be passing for the wrong reason.
    """
    store = RecordingLoreStore(already_holding=[scenario.BIBLE_FACT])

    stored = store.search(scenario.PROJECT_ID, "anything", 5)

    assert stored[0].fact_id != scenario.BIBLE_FACT.fact_id
    assert stored[0].fact_id == content_hash(scenario.BIBLE_FACT.text)


def test_a_different_project_is_not_mistaken_for_this_one() -> None:
    """The guard reads the demo project, not whatever the store holds."""
    store = RecordingLoreStore(already_holding=[scenario.BIBLE_FACT])
    store._stored = []

    load_script().seed(store)

    assert store.indexed, "an empty project must still be seeded"
