"""Unit tests for `ListScripts` (docs/api/openapi.yaml,
`GET /api/projects/{project_id}/scripts`).

The shared `FakeScriptStore` and `FakeFindingStore` cover the reads. The
failure path needs a store that raises, which this file writes locally --
with a plain `SourceUnavailable`, since neither `application/` nor its tests
import `clearcut.adapters` (AGENT.md Section 2 rule 2).

Hand-written fakes only, no `unittest.mock`, no network (AGENT.md Section 5).
"""

import pytest

from clearcut.application.list_scripts import ListScripts, ScriptListing
from clearcut.application.ports import ScriptStore
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.finding import Category, Finding, NerLabel, RiskLevel
from clearcut.domain.script import Scene, Script
from tests.unit.fakes import FakeFindingStore, FakeScriptStore


def _script(script_id: str, project_id: str, version: int) -> Script:
    return Script(
        script_id=script_id,
        project_id=project_id,
        version=version,
        gcs_uri=f"gs://clearcut-scripts/{project_id}/{script_id}.pdf",
        jurisdiction_code="AR",
        scenes=[
            Scene(
                number=1,
                heading="INT. BAR NOTTURNO - NIGHT",
                page_start=1,
                page_end=2,
                text="MARA drinks a Coca-Cola.",
            )
        ],
    )


def _finding(finding_id: str) -> Finding:
    return Finding(
        finding_id=finding_id,
        scene_number=1,
        page=1,
        raw_text="Coca-Cola",
        category=Category.INDUSTRIAL_PROPERTY,
        ner_label=NerLabel.BRAND,
        risk_level=RiskLevel.HIGH,
        required_document="Brand clearance",
    )


class _FailingScriptStore:
    """`for_project` is the only method `ListScripts` calls, and here it
    refuses; the other three raise if reached, so a mistaken extra call fails
    loudly."""

    def save(self, script: Script) -> None:
        raise NotImplementedError

    def get(self, project_id: str, script_id: str) -> Script:
        raise NotImplementedError

    def for_project(self, project_id: str) -> list[Script]:
        raise SourceUnavailable("clickhouse did not answer")

    def latest(self, project_id: str) -> Script | None:
        raise NotImplementedError


_conforms: ScriptStore = _FailingScriptStore()


def test_failing_script_store_satisfies_the_scriptstore_port() -> None:
    assert isinstance(_conforms, ScriptStore)


def test_execute_returns_every_version_newest_first() -> None:
    scripts = FakeScriptStore(
        [
            _script("scr-1", "prj-4f2a", 1),
            _script("scr-3", "prj-4f2a", 3),
            _script("scr-2", "prj-4f2a", 2),
        ]
    )
    use_case = ListScripts(scripts, FakeFindingStore())

    result = use_case.execute("prj-4f2a")

    assert [listing.script.version for listing in result] == [3, 2, 1]


def test_two_versions_with_the_same_number_answer_most_recent_first() -> None:
    """Sorting on `version` alone leaves ties in store order, which is oldest
    first, so the older of two equal versions won the top of the list.

    That is not academic. The mock scenario seeds `demo-script-v1` at version
    1 as a script that exists but was never analyzed, and an analysis posted
    at version 1 writes a second row at the same number. The client takes the
    first entry, so Script Review drew the seeded text with none of the
    findings the run had just produced -- the empty screen ADR 0014 exists to
    end, reappearing through the ordering rather than the storage.
    """
    scripts = FakeScriptStore(
        [
            _script("seeded", "prj-4f2a", 1),
            _script("analyzed", "prj-4f2a", 1),
        ]
    )
    use_case = ListScripts(scripts, FakeFindingStore())

    result = use_case.execute("prj-4f2a")

    assert [listing.script.script_id for listing in result] == ["analyzed", "seeded"]


def test_execute_counts_the_findings_of_each_version_separately() -> None:
    """Findings are stored per version, so reopening an older one shows what
    that version triggered rather than what the newest one does."""
    scripts = FakeScriptStore([_script("scr-1", "prj-4f2a", 1), _script("scr-2", "prj-4f2a", 2)])
    findings = FakeFindingStore()
    findings.save("prj-4f2a", "scr-1", [_finding("EVT-001")])
    findings.save("prj-4f2a", "scr-2", [_finding("EVT-001"), _finding("EVT-002")])

    result = ListScripts(scripts, findings).execute("prj-4f2a")

    assert result == [
        ScriptListing(script=scripts.get("prj-4f2a", "scr-2"), finding_count=2),
        ScriptListing(script=scripts.get("prj-4f2a", "scr-1"), finding_count=1),
    ]


def test_execute_ignores_another_projects_versions() -> None:
    scripts = FakeScriptStore([_script("scr-1", "prj-4f2a", 1), _script("scr-9", "prj-0000", 1)])

    result = ListScripts(scripts, FakeFindingStore()).execute("prj-4f2a")

    assert [listing.script.script_id for listing in result] == ["scr-1"]


def test_execute_returns_an_empty_list_for_a_project_with_no_script() -> None:
    """The contract's 404 on this path is about an unknown project, which
    `ScriptStore` cannot tell apart from a project that has never had a script
    analyzed, so the route owns that distinction."""
    use_case = ListScripts(FakeScriptStore(), FakeFindingStore())

    assert use_case.execute("prj-4f2a") == []


def test_execute_propagates_a_store_failure_unchanged() -> None:
    use_case = ListScripts(_FailingScriptStore(), FakeFindingStore())

    with pytest.raises(SourceUnavailable, match="clickhouse did not answer"):
        use_case.execute("prj-4f2a")
