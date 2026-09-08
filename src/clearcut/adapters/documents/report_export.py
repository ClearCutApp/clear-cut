"""Render saved report snapshots; never query changing operational state."""

import csv
import unicodedata
from html import escape
from io import BytesIO, StringIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer

from clearcut.adapters.documents import pdf_fonts


class _ItemParagraph(Paragraph):  # type: ignore[misc]
    item_id: str = ""

    def split(self, width: float, height: float) -> list[Any]:
        parts: list[Any] = super().split(width, height)
        for part in parts:
            part.item_id = self.item_id
        return parts


def spreadsheet_text(value: object) -> str:
    text = str(value or "")
    probe = text
    while probe and (probe[0].isspace() or unicodedata.category(probe[0]) in {"Cc", "Cf"}):
        probe = probe[1:]
    if probe.startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


class ClearanceReportRenderer:
    def csv(self, snapshot: dict[str, Any]) -> bytes:
        output = StringIO(newline="")
        writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
        headers = [
            "report_id",
            "project",
            "report_revision",
            "total_retained",
            "confirmed_cleared",
            "item_id",
            "item_version",
            "asset",
            "category",
            "state",
            "needs_review",
            "present_in_revision",
            "finding_revision",
            "page",
            "due_date",
            "assignee",
            "conditions",
            "note",
            "evidence_ids",
            "request_draft",
            "citations",
            "local_research_ids",
            "local_coverage_gaps",
            "local_research_sha256",
        ]
        writer.writerow(headers)
        findings = {value["finding_id"]: value for value in snapshot["findings"]}
        for item in snapshot["tracker_items"]:
            finding = findings.get(item["finding_id"], {})
            binding = snapshot["clearance_bindings"].get(item["item_id"], {})
            citations = [*finding.get("citations", []), *item.get("rights_holder_citations", [])]
            values = [
                snapshot["report_id"],
                snapshot["project_title"],
                snapshot["revision_id"],
                snapshot["counts"]["total_retained"],
                snapshot["counts"]["confirmed_cleared"],
                item["item_id"],
                item["version"],
                finding.get("raw_text", ""),
                finding.get("category", ""),
                item["state"],
                item["needs_review"],
                binding.get("present", "unknown"),
                binding.get("revision_id", "unknown"),
                finding.get("page", ""),
                item.get("due_date", ""),
                item.get("assignee_id", ""),
                item.get("clearance_conditions", ""),
                item.get("note", ""),
                " | ".join(item.get("evidence_file_ids", [])),
                item.get("draft_email", ""),
                " | ".join(citation["uri"] for citation in citations),
                " | ".join(record["research_id"] for record in snapshot.get("local_research", [])),
                " | ".join(
                    value["location"].get("location", "")
                    for value in snapshot.get("location_coverage", [])
                    if value["status"] == "coverage_gap"
                ),
                snapshot.get("local_research_sha256", ""),
            ]
            writer.writerow(
                [
                    value if isinstance(value, (int, float, bool)) else spreadsheet_text(value)
                    for value in values
                ]
            )
        return output.getvalue().encode("utf-8-sig")

    def pdf(self, snapshot: dict[str, Any]) -> bytes:
        pdf_fonts.register()
        output = BytesIO()
        spanish = snapshot["language"] == "es"

        def text(en: str, es: str) -> str:
            return es if spanish else en

        body = ParagraphStyle(
            "ReportBody",
            fontName=pdf_fonts.REGULAR,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#17212b"),
            spaceAfter=6,
            alignment=TA_LEFT,
        )
        heading = ParagraphStyle(
            "ReportHeading",
            parent=body,
            fontName=pdf_fonts.BOLD,
            fontSize=13,
            leading=17,
            spaceBefore=12,
        )
        title = ParagraphStyle("ReportTitle", parent=heading, fontSize=21, leading=25)

        active_item = ""

        def paragraph(value: object, style: ParagraphStyle = body) -> Paragraph:
            result = _ItemParagraph(escape(pdf_fonts.text(value)).replace("\n", "<br/>"), style)
            result.item_id = active_item
            return result

        counts = snapshot["counts"]
        story: list[Any] = [
            paragraph(text("Clearance report", "Informe de autorizaciones"), title),
            paragraph(snapshot["project_title"], heading),
            paragraph(f"{snapshot['revision_id']} · {snapshot['created_at']}"),
            paragraph(
                text(
                    "Fixed snapshot of recorded decisions. AI findings are not legal clearance.",
                    "Instantánea fija de decisiones registradas. Los hallazgos de IA no "
                    "constituyen autorización legal.",
                )
            ),
            paragraph(
                text(
                    f"Human-confirmed cleared: {counts['confirmed_cleared']} of "
                    f"{counts['total_retained']} retained items "
                    f"({counts['confirmed_cleared_percent']}%).",
                    f"Autorizaciones confirmadas por personas: "
                    f"{counts['confirmed_cleared']} de {counts['total_retained']} elementos "
                    f"conservados ({counts['confirmed_cleared_percent']}%).",
                )
            ),
            paragraph(
                text(
                    f"Needs review: {counts['needs_review']} · Blocked: {counts['blocked']} "
                    f"· In progress: {counts['in_progress']}.",
                    f"Requieren revisión: {counts['needs_review']} · Bloqueados: "
                    f"{counts['blocked']} · En curso: {counts['in_progress']}.",
                )
            ),
            paragraph(
                text(
                    f"Present: {counts['present']} · Not detected: {counts['not_detected']} "
                    f"· Unknown binding: {counts['unknown_binding']}.",
                    f"Presentes: {counts['present']} · No detectados: "
                    f"{counts['not_detected']} · Vínculo desconocido: {counts['unknown_binding']}.",
                )
            ),
            paragraph(
                text(
                    "Denominator: all retained items. CLEARED items awaiting review are "
                    "excluded from confirmed clearance; review takes precedence over "
                    "recorded state. An empty report is 0%.",
                    "Denominador: todos los elementos conservados. CLEARED pendiente de "
                    "revisión no cuenta como autorización confirmada; la revisión tiene "
                    "prioridad sobre el estado. Un informe vacío representa 0%.",
                )
            ),
            paragraph(f"{snapshot['formula_version']} · {snapshot['template_version']}"),
        ]
        if snapshot.get("draft_newer_at_capture"):
            story.append(
                paragraph(
                    text(
                        "A newer draft existed when this report was captured.",
                        "Existía un borrador más reciente al capturar este informe.",
                    )
                )
            )
        if snapshot.get("production_context_changed_at_capture"):
            story.append(
                paragraph(
                    text(
                        "Production locations or jurisdiction changed after this analysis.",
                        "Las ubicaciones o la jurisdicción cambiaron después de este análisis.",
                    )
                )
            )
        if snapshot.get("coverage_gaps"):
            story.append(
                paragraph(
                    text(
                        "Coverage gaps: some research lacks verified cited evidence.",
                        "Lagunas de cobertura: parte de la investigación carece de "
                        "evidencia citada verificada.",
                    )
                )
            )
        findings = {value["finding_id"]: value for value in snapshot["findings"]}
        evidence = {value["file_id"]: value for value in snapshot.get("evidence", [])}
        for item in snapshot["tracker_items"]:
            active_item = item["item_id"]
            item_story: list[Any] = []
            finding = findings.get(item["finding_id"], {})
            binding = snapshot["clearance_bindings"].get(item["item_id"], {})
            label = finding.get("raw_text") or item["required_document"] or item["item_id"]
            item_story.extend(
                [
                    Spacer(1, 4 * mm),
                    paragraph(label, heading),
                    paragraph(
                        f"{item['item_id']} · v{item['version']} · "
                        + (
                            {
                                "CLEARED": "Autorizado",
                                "BLOCKED": "Bloqueado",
                                "IN_PROGRESS": "En curso",
                            }.get(item["state"], item["state"])
                            if spanish
                            else item["state"].replace("_", " ").title()
                        )
                        + (
                            text(" · NEEDS REVIEW", " · REQUIERE REVISIÓN")
                            if item["needs_review"]
                            else ""
                        )
                    ),
                ]
            )
            item_story.append(
                paragraph(
                    text("Finding revision", "Revisión del hallazgo")
                    + f": {binding.get('revision_id', 'unknown')} · "
                    + text("Page", "Página")
                    + f" {finding.get('page', '—')}"
                )
            )
            if binding.get("present") is False:
                item_story.append(
                    paragraph(
                        text(
                            "Not detected in the selected revision; original finding "
                            "reference retained.",
                            "No detectado en la revisión seleccionada; se conserva la "
                            "referencia original.",
                        )
                    )
                )
            for label, value in [
                (text("Required document", "Documento requerido"), item["required_document"]),
                (text("Due date", "Fecha límite"), item.get("due_date")),
                (text("Conditions", "Condiciones"), item.get("clearance_conditions")),
                (text("Note", "Nota"), item.get("note")),
            ]:
                if value:
                    item_story.append(paragraph(f"{label}: {value}"))
            for file_id in item.get("evidence_file_ids", []):
                proof = evidence.get(file_id, {})
                item_story.append(
                    paragraph(
                        text("Evidence", "Evidencia")
                        + f": {proof.get('filename', file_id)} · SHA-256 "
                        + str(proof.get("sha256", "unknown"))
                    )
                )
            for citation in [
                *finding.get("citations", []),
                *item.get("rights_holder_citations", []),
            ]:
                item_story.append(
                    paragraph(
                        f"{citation.get('title', '')}\n{citation['uri']}\n"
                        f"{citation.get('snippet', '')}"
                    )
                )
            story.append(KeepTogether(item_story))

        if "local_research" in snapshot:
            active_item = ""
            story.append(
                paragraph(
                    text("Production location research", "Investigación de ubicaciones"), heading
                )
            )
            story.append(
                paragraph(
                    text(
                        "Recorded evidence is not permit approval or legal clearance. "
                        "Authorities, fees and requirements must be confirmed for the "
                        "actual production.",
                        "La evidencia registrada no constituye aprobación de permisos ni "
                        "autorización "
                        "legal. Deben confirmarse las autoridades, tasas y requisitos de la "
                        "producción concreta.",
                    )
                )
            )
            window = snapshot.get("local_research_history_window", 0)
            story.append(
                paragraph(
                    text(
                        f"Captured research window: latest {window} records. Older records may be "
                        "omitted; a coverage gap remains when current location evidence is absent.",
                        f"Ventana capturada: últimos {window} registros. Puede haber registros "
                        "anteriores omitidos; falta cobertura cuando no hay evidencia actual "
                        "de la ubicación.",
                    )
                )
            )
            coverage = snapshot.get("location_coverage", [])
            if not coverage:
                story.append(
                    paragraph(
                        text(
                            "Coverage gap: no production locations selected.",
                            "Laguna de cobertura: no se seleccionaron ubicaciones de producción.",
                        )
                    )
                )
            for value in coverage:
                location = value["location"]
                status = (
                    text(
                        "Evidence recorded; confirmation required",
                        "Evidencia registrada; requiere confirmación",
                    )
                    if value["status"] == "evidence_recorded"
                    else text("Coverage gap", "Laguna de cobertura")
                )
                story.append(
                    paragraph(
                        f"{location.get('country', '')} · {location.get('location', '')}: {status}"
                    )
                )
            story.append(paragraph("SHA-256: " + snapshot.get("local_research_sha256", "unknown")))
            for record in snapshot["local_research"]:
                active_item = record["research_id"]
                story.append(paragraph(record["question"], heading))
                story.append(
                    paragraph(
                        f"{record['research_id']} · {record['created_at']} · "
                        f"{record.get('provider', 'unknown')}"
                    )
                )
                location = record.get("location", {})
                story.append(
                    paragraph(f"{location.get('country', '')} · {location.get('location', '')}")
                )
                for citation in record.get("citations", []):
                    story.append(paragraph(f"{citation.get('title', '')} · {citation['uri']}"))
                    snippet = citation.get("snippet", "")
                    story.append(paragraph(snippet[:2000]))
                    if len(snippet) > 2000:
                        story.append(
                            paragraph(
                                text(
                                    "Excerpt; full source quotation is retained in the immutable "
                                    "report snapshot.",
                                    "Extracto; la cita completa se conserva en la instantánea "
                                    "inmutable del informe.",
                                )
                            )
                        )
                if not record.get("citations"):
                    story.append(
                        paragraph(
                            text(
                                "Coverage gap: no cited official evidence recorded.",
                                "Laguna de cobertura: no se registró evidencia oficial citada.",
                            )
                        )
                    )

        page_items: list[str] = []

        def record_item(flowable: Any) -> None:
            item_id = getattr(flowable, "item_id", "")
            if item_id and item_id not in page_items:
                page_items.append(item_id)

        def footer(canvas: Any, document: Any) -> None:
            canvas.saveState()
            canvas.setFont(pdf_fonts.REGULAR, 8)
            canvas.drawString(18 * mm, 12 * mm, f"ClearCut · {snapshot['report_id']}")
            canvas.drawRightString(
                A4[0] - 18 * mm, 12 * mm, text("Page", "Página") + f" {document.page}"
            )
            if page_items:
                label = page_items[0] + (" … " + page_items[-1] if len(page_items) > 1 else "")
                canvas.drawString(
                    18 * mm, 17 * mm, text("References", "Referencias") + ": " + label
                )
            page_items.clear()
            canvas.restoreState()

        document = SimpleDocTemplate(
            output,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=22 * mm,
            title="ClearCut clearance report",
        )
        document.afterFlowable = record_item
        document.afterPage = lambda: footer(document.canv, document)
        document.build(story)
        return output.getvalue()
