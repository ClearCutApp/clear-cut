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

SCRIPT = Path(__file__).resolve().parents[3] / "infra" / "seed_project_bible.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seed_project_bible", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RecordingLoreStore:
    """Records what was indexed. The seam `seed` takes, so this test needs no
    BigQuery dataset and no credentials."""

    def __init__(self) -> None:
        self.indexed: list[tuple[str, list[Any]]] = []

    def index(self, project_id: str, records: list[Any]) -> None:
        self.indexed.append((project_id, records))

    def search(self, project_id: str, query: str, limit: int) -> list[Any]:
        raise AssertionError("seeding must not read")


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
