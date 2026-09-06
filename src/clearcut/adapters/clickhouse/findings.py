"""Persists the findings of one analysis over ClickHouse (ADR 0014).

Before this table a `Finding` lived only inside the response that reported
it. `AnalyzeScript` returned an `AnalysisReport`, the route serialized it, and
that was the last time the evidence existed: reloading Script Review rendered
nothing, and a tracker item could show its state and its contact but not what
was found, where, or under which law. The tracker item is the actionable side
of a finding, not the finding.

Findings are keyed by script version, not by project. Reopening version 1 has
to show what version 1 triggered rather than what the newest one does, so
`script_id` sits between the project and the finding in the sort key.

`citations` crosses as a JSON string in one `String` column. A `Nested` type
would let ClickHouse index inside a citation, which nothing here asks it to
do, and would cost a second schema to keep in step with `domain/finding.py`.
"""

from __future__ import annotations

import json
from typing import Any

from clearcut.adapters.clickhouse import client as ch_client
from clearcut.adapters.clickhouse import schema
from clearcut.domain.finding import Category, Citation, Finding, NerLabel, RiskLevel

FINDING_COLUMNS = [
    "project_id",
    "script_id",
    "finding_id",
    "scene_number",
    "page",
    "raw_text",
    "category",
    "ner_label",
    "risk_level",
    "required_document",
    "citations",
    "contradicts",
]


class ClickHouseFindingStore:
    """Implements `FindingStore` over a ClickHouse Cloud HTTPS connection."""

    def __init__(self, client: ch_client._ChClient) -> None:
        self._client = client

    def ensure_schema(self) -> None:
        schema.ensure_schema(self._client)

    def save(self, project_id: str, script_id: str, findings: list[Finding]) -> None:
        if not findings:
            return
        rows = [finding_to_row(project_id, script_id, finding) for finding in findings]
        try:
            self._client.insert("findings", rows, FINDING_COLUMNS)
        except Exception as exc:
            raise ch_client.ClickHouseUnavailable(
                f"failed to save {len(findings)} finding(s) for script {script_id!r}: {exc}"
            ) from exc

    def for_script(self, project_id: str, script_id: str) -> list[Finding]:
        try:
            result = self._client.query(
                "SELECT * FROM findings "
                "WHERE project_id = {project_id:String} AND script_id = {script_id:String}",
                {"project_id": project_id, "script_id": script_id},
            )
        except Exception as exc:
            raise ch_client.ClickHouseUnavailable(f"failed to query findings: {exc}") from exc
        project_index = FINDING_COLUMNS.index("project_id")
        script_index = FINDING_COLUMNS.index("script_id")
        matching = [
            row
            for row in result.result_rows
            if row[project_index] == project_id and row[script_index] == script_id
        ]
        findings = [row_to_finding(row) for row in matching]
        return sorted(findings, key=lambda finding: (finding.scene_number, finding.finding_id))


def finding_to_row(project_id: str, script_id: str, finding: Finding) -> list[Any]:
    citations = [
        {"uri": citation.uri, "title": citation.title, "snippet": citation.snippet}
        for citation in finding.citations
    ]
    return [
        project_id,
        script_id,
        finding.finding_id,
        finding.scene_number,
        finding.page,
        finding.raw_text,
        finding.category.value,
        finding.ner_label.value if finding.ner_label is not None else None,
        finding.risk_level.value,
        finding.required_document,
        json.dumps(citations),
        finding.contradicts,
    ]


def row_to_finding(row: tuple[Any, ...]) -> Finding:
    values = dict(zip(FINDING_COLUMNS, row, strict=True))
    citations = tuple(
        Citation(uri=raw["uri"], title=raw["title"], snippet=raw["snippet"])
        for raw in json.loads(values["citations"])
    )
    return Finding(
        finding_id=values["finding_id"],
        scene_number=int(values["scene_number"]),
        page=int(values["page"]),
        raw_text=values["raw_text"],
        category=Category(values["category"]),
        ner_label=_ner_label(values["ner_label"]),
        risk_level=RiskLevel(values["risk_level"]),
        required_document=values["required_document"],
        citations=citations,
        contradicts=values["contradicts"] or None,
    )


def _ner_label(stored: str | None) -> NerLabel | None:
    """`None` for a `CONTINUITY` or `POLICY` finding, which carries no label.

    The empty string is folded into `None` as well: a `Nullable(String)` read
    back through a driver setting that prefers defaults over nulls hands the
    column's zero value across, and `Finding` refuses a label on those two
    categories -- so the difference decides whether the row reconstructs at
    all.
    """
    return NerLabel(stored) if stored else None
