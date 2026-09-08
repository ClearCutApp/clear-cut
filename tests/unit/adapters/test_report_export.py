"""Saved-report totals, pagination and spreadsheet-safe untrusted cells."""

import csv
from dataclasses import replace
from io import BytesIO, StringIO
from typing import Any

import pytest
from pypdf import PdfReader

from clearcut.adapters.documents.report_export import ClearanceReportRenderer, spreadsheet_text
from clearcut.application.analysis_documents import finding_data, tracker_data
from clearcut.domain.report import clearance_counts
from clearcut.domain.tracker import TrackerState
from tests.unit.adapters.test_clearance_transactions import item
from tests.unit.application.test_analyze_script import _finding


def report_snapshot(count: int = 3, language: str = "es") -> dict[str, Any]:
    items = [
        replace(
            item(),
            item_id=f"item-{number}",
            finding_id=f"item-{number}",
            state=TrackerState.CLEARED if number % 2 == 0 else TrackerState.BLOCKED,
            needs_review=number == 0,
            note="¿Autorización de música en México? <img src='https://invalid.example'>",
            clearance_conditions="Sólo Argentina y México; una película.",
            draft_email='\t =HYPERLINK("https://invalid.example","unsafe")',
        )
        for number in range(count)
    ]
    bindings = {
        item.item_id: {"revision_id": "revision-1", "present": number != 0}
        for number, item in enumerate(items)
    }
    return {
        "report_id": "synthetic-report",
        "project_title": "La última escena",
        "revision_id": "revision-1",
        "created_at": "2026-09-06T18:00:00Z",
        "language": language,
        "formula_version": "clearance-counts-v1",
        "template_version": "clearance-report-v1",
        "counts": clearance_counts(items, bindings),
        "tracker_items": [tracker_data(item) for item in items],
        "findings": [
            finding_data(_finding(finding_id=item.finding_id, raw_text=f"Música {number}"))
            for number, item in enumerate(items)
        ],
        "clearance_bindings": bindings,
        "evidence": [],
        "coverage_gaps": [],
        "draft_newer_at_capture": True,
    }


@pytest.mark.parametrize(
    "value", ["=1+1", "  +SUM(A1)", "\t-1+2", "\r\n@SUM(A1)", "\ufeff=1+1", "\u200b=1+1"]
)
def test_formula_like_text_is_neutralized_without_changing_canonical_content(value):
    assert spreadsheet_text(value) == "'" + value


def test_report_csv_quotes_newlines_and_keeps_numeric_totals_consistent():
    snapshot = report_snapshot()
    snapshot["tracker_items"][1]["note"] = 'Line one\n"quoted", México'
    encoded = ClearanceReportRenderer().csv(snapshot)
    rows = list(csv.DictReader(StringIO(encoded.decode("utf-8-sig"))))
    assert len(rows) == 3
    assert {row["total_retained"] for row in rows} == {"3"}
    assert {row["confirmed_cleared"] for row in rows} == {"1"}
    assert rows[0]["request_draft"].startswith("'\t =HYPERLINK")
    assert rows[1]["note"] == 'Line one\n"quoted", México'
    assert snapshot["tracker_items"][0]["draft_email"].startswith("\t =HYPERLINK")


def test_report_pdf_carries_all_175_items_and_excludes_pending_review_from_confirmed_count():
    snapshot = report_snapshot(175)
    pdf = PdfReader(BytesIO(ClearanceReportRenderer().pdf(snapshot)))
    text = " ".join(page.extract_text() for page in pdf.pages)
    assert len(pdf.pages) > 2
    assert "87 de 175" in text
    assert "Música 174" in text and "item-174" in text
    assert "<img src='https://invalid.example'>" in text
    assert "No detectado en la revisión seleccionada" in text
    assert "Sólo Argentina y México" in text


def test_empty_report_has_explicit_zero_denominator():
    snapshot = report_snapshot(0, "en")
    text = PdfReader(BytesIO(ClearanceReportRenderer().pdf(snapshot))).pages[0].extract_text()
    assert "0 of 0 retained items (0.0%)" in text


def test_report_embeds_extended_latin_and_names_unsupported_symbols_readably():
    snapshot = report_snapshot(1)
    snapshot["project_title"] = "Montréal · São Paulo · Zoë · Łukasz · 🎬"
    reader = PdfReader(BytesIO(ClearanceReportRenderer().pdf(snapshot)))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "Łukasz" in text and "[CLAPPER BOARD]" in text
    resources: Any = reader.pages[0]["/Resources"]
    fonts = resources["/Font"].get_object()
    assert any(font.get_object().get("/Subtype") == "/TrueType" for font in fonts.values())


def local_report_snapshot() -> dict[str, Any]:
    snapshot = report_snapshot(2, "es")
    snapshot.update(
        {
            "template_version": "clearance-report-v2",
            "local_research_history_window": 50,
            "local_research_sha256": "a" * 64,
            "location_coverage": [
                {
                    "location": {"country": "AR", "location": "Buenos Aires"},
                    "status": "evidence_recorded",
                    "research_ids": ["research-1"],
                },
                {
                    "location": {"country": "MX", "location": " =UNTRUSTED()"},
                    "status": "coverage_gap",
                    "research_ids": [],
                },
            ],
            "local_research": [
                {
                    "research_id": "research-1",
                    "question": "¿Podemos cerrar esta calle? Łukasz 🎬",
                    "created_at": "2026-09-06T12:00:00Z",
                    "provider": "Parallel Search",
                    "location": {"country": "AR", "location": "Buenos Aires"},
                    "citations": [
                        {
                            "uri": "https://buenosaires.gob.ar/rodajes/" + "long-segment/" * 25,
                            "title": "Fuente oficial",
                            "snippet": "Consultar a la autoridad; no es permiso. " * 100,
                        }
                    ],
                }
            ],
        }
    )
    return snapshot


def test_local_report_derivatives_preserve_evidence_identity_and_explicit_gaps():
    snapshot = local_report_snapshot()
    renderer = ClearanceReportRenderer()
    reader = PdfReader(BytesIO(renderer.pdf(snapshot)))
    content = " ".join(page.extract_text() for page in reader.pages)
    assert "research-1" in content and "Laguna de cobertura" in content
    assert "Fuente oficial" in content and "Extracto;" in content
    assert "a" * 64 in content.replace(" ", "").replace("\n", "")
    rows = list(csv.DictReader(StringIO(renderer.csv(snapshot).decode("utf-8-sig"))))
    assert rows[0]["local_research_ids"] == "research-1"
    assert rows[0]["local_research_sha256"] == "a" * 64
    assert rows[0]["local_coverage_gaps"] == "' =UNTRUSTED()"
    assert snapshot["location_coverage"][1]["location"]["location"] == " =UNTRUSTED()"
