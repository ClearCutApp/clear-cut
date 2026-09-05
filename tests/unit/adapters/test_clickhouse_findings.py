"""Unit tests for the ClickHouse-backed `FindingStore` (ADR 0014).

Before this table a `Finding` existed only inside the response that reported
it: `AnalyzeScript` returned it, the route serialized it, and reloading Script
Review rendered nothing. The round trips below are what make the evidence
survive the response -- the citations, the null `ner_label` a bible finding
carries, and the `contradicts` fact id.
"""

from __future__ import annotations

import pytest

from clearcut.adapters.clickhouse.client import ClickHouseUnavailable
from clearcut.adapters.clickhouse.findings import ClickHouseFindingStore, finding_to_row
from clearcut.application.ports import FindingStore
from clearcut.domain.finding import Category, Citation, Finding, NerLabel, RiskLevel
from tests.unit.adapters.fake_ch_client import ExplodingChClient, FakeChClient

_CITATION = Citation(
    uri="https://servicios.infoleg.gob.ar/infolegInternet/anexos/40000-44999/42755/texact.htm",
    title="Ley 11.723, Regimen Legal de la Propiedad Intelectual",
    snippet="Articulo 1",
)


def _finding(
    finding_id: str = "EVT-014",
    scene_number: int = 12,
    category: Category = Category.INDUSTRIAL_PROPERTY,
    ner_label: NerLabel | None = NerLabel.BRAND,
    citations: tuple[Citation, ...] = (_CITATION,),
    contradicts: str | None = None,
) -> Finding:
    return Finding(
        finding_id=finding_id,
        scene_number=scene_number,
        page=14,
        raw_text="a Coca-Cola sign flickers above the bar",
        category=category,
        ner_label=ner_label,
        risk_level=RiskLevel.HIGH,
        required_document="Trademark Use Authorization",
        citations=citations,
        contradicts=contradicts,
    )


def test_adapter_satisfies_the_findingstore_port() -> None:
    adapter = ClickHouseFindingStore(FakeChClient())
    checked: FindingStore = adapter
    assert isinstance(checked, FindingStore)


def test_ensure_schema_keys_findings_on_project_script_and_finding() -> None:
    """Finding ids come from the same per-analysis sequence tracker item ids
    do, so the project and the script version both have to be in the key or
    two versions' `EVT-014` are one row."""
    client = FakeChClient()

    ClickHouseFindingStore(client).ensure_schema()

    ddl = next(cmd for cmd in client.commands if "CREATE TABLE IF NOT EXISTS findings" in cmd)
    assert "ORDER BY (project_id, script_id, finding_id)" in ddl


def test_save_inserts_one_row_per_finding_carrying_the_script_it_belongs_to() -> None:
    client = FakeChClient()

    ClickHouseFindingStore(client).save(
        "prj-a", "scr-1", [_finding("EVT-001"), _finding("EVT-002")]
    )

    table, rows, columns = client.inserts[0]
    assert table == "findings"
    assert len(rows) == 2
    assert {row[columns.index("script_id")] for row in rows} == {"scr-1"}
    assert {row[columns.index("finding_id")] for row in rows} == {"EVT-001", "EVT-002"}


def test_save_of_nothing_issues_no_insert() -> None:
    """An analysis that raised no finding is a clean script, not a reason to
    hand ClickHouse an empty batch."""
    client = FakeChClient()

    ClickHouseFindingStore(client).save("prj-a", "scr-1", [])

    assert client.inserts == []


def test_for_script_round_trips_the_citations() -> None:
    client = FakeChClient()
    adapter = ClickHouseFindingStore(client)
    finding = _finding()
    client.set_result([tuple(finding_to_row("prj-a", "scr-1", finding))])

    result = adapter.for_script("prj-a", "scr-1")

    assert result == [finding]
    assert result[0].citations[0].uri == _CITATION.uri
    assert result[0].citations[0].snippet == "Articulo 1"


def test_for_script_round_trips_a_bible_finding_with_no_ner_label() -> None:
    """`CONTINUITY` and `POLICY` findings carry no label at all, and `Finding`
    raises if one is attached -- so a `Nullable(String)` that reads back as
    the empty string instead of `None` fails construction, not silently."""
    client = FakeChClient()
    adapter = ClickHouseFindingStore(client)
    finding = _finding(
        category=Category.CONTINUITY,
        ner_label=None,
        citations=(),
        contradicts="FACT-007",
    )
    client.set_result([tuple(finding_to_row("prj-a", "scr-1", finding))])

    result = adapter.for_script("prj-a", "scr-1")

    assert result[0].ner_label is None
    assert result[0].contradicts == "FACT-007"
    assert result[0].citations == ()


def test_for_script_excludes_findings_from_another_version_of_the_same_project() -> None:
    """Reopening version 1 must show what version 1 triggered, not what
    version 2 does."""
    client = FakeChClient()
    adapter = ClickHouseFindingStore(client)
    client.set_result(
        [
            tuple(finding_to_row("prj-a", "scr-1", _finding("EVT-001"))),
            tuple(finding_to_row("prj-a", "scr-2", _finding("EVT-002"))),
        ]
    )

    assert [finding.finding_id for finding in adapter.for_script("prj-a", "scr-1")] == ["EVT-001"]


def test_for_script_orders_findings_by_scene_then_id() -> None:
    client = FakeChClient()
    adapter = ClickHouseFindingStore(client)
    client.set_result(
        [
            tuple(finding_to_row("prj-a", "scr-1", _finding("EVT-009", scene_number=40))),
            tuple(finding_to_row("prj-a", "scr-1", _finding("EVT-002", scene_number=3))),
            tuple(finding_to_row("prj-a", "scr-1", _finding("EVT-001", scene_number=3))),
        ]
    )

    assert [finding.finding_id for finding in adapter.for_script("prj-a", "scr-1")] == [
        "EVT-001",
        "EVT-002",
        "EVT-009",
    ]


def test_for_script_returns_an_empty_list_for_a_script_with_no_findings() -> None:
    client = FakeChClient()
    client.set_result([])

    assert ClickHouseFindingStore(client).for_script("prj-a", "scr-1") == []


def test_ensure_schema_wraps_a_client_error_as_clickhouse_unavailable() -> None:
    with pytest.raises(ClickHouseUnavailable):
        ClickHouseFindingStore(ExplodingChClient()).ensure_schema()


def test_save_wraps_a_client_error_as_clickhouse_unavailable() -> None:
    with pytest.raises(ClickHouseUnavailable):
        ClickHouseFindingStore(ExplodingChClient()).save("prj-a", "scr-1", [_finding()])


def test_for_script_wraps_a_client_error_as_clickhouse_unavailable() -> None:
    with pytest.raises(ClickHouseUnavailable):
        ClickHouseFindingStore(ExplodingChClient()).for_script("prj-a", "scr-1")
