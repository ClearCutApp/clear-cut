"""Download a human-reviewed request draft; generating it never sends outreach."""

from html import escape
from io import BytesIO

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from clearcut.domain.tracker import TrackerItem


def permission_pdf(item: TrackerItem, project_title: str = "") -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=letter,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
        title="Permission request draft",
    )
    body = ParagraphStyle(
        "request",
        fontName="Helvetica",
        fontSize=11,
        leading=16,
        alignment=TA_LEFT,
        spaceAfter=10,
        splitLongWords=True,
    )
    heading = ParagraphStyle(
        "heading", parent=body, fontName="Helvetica-Bold", fontSize=18, leading=23
    )
    small = ParagraphStyle("details", parent=body, fontSize=9, leading=13)
    story = [
        Paragraph("Permission request — draft", heading),
        Paragraph(
            f"{escape(project_title or item.project_id)} · Version {item.version}",
            small,
        ),
        Paragraph(f"Request: {escape(item.required_document)}", body),
        Paragraph(f"Reference: {escape(item.item_id)}", small),
        Paragraph("For human review. This document does not confirm legal clearance.", small),
        Spacer(1, 0.2 * inch),
    ]
    for paragraph in (item.draft_email or "").split("\n"):
        story.append(Paragraph(escape(paragraph) or "&#160;", body))
    if item.clearance_conditions:
        story.extend(
            [
                Spacer(1, 0.2 * inch),
                Paragraph("Proposed scope / conditions", heading),
                Paragraph(escape(item.clearance_conditions).replace("\n", "<br/>"), body),
            ]
        )

    def footer(canvas: Canvas, _: SimpleDocTemplate) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(inch, 0.55 * inch, f"Draft only · Version {item.version}")
        canvas.drawRightString(letter[0] - inch, 0.55 * inch, str(canvas.getPageNumber()))
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


def permission_document(item: TrackerItem, format_name: str, project_title: str = "") -> bytes:
    if format_name == "pdf":
        return permission_pdf(item, project_title)
    text = (
        f"Permission request — draft\n{project_title or item.project_id}\n"
        f"Request: {item.required_document}\nReference: {item.item_id}, version {item.version}\n\n"
        f"{item.draft_email or ''}"
    )
    if item.clearance_conditions:
        text += f"\n\nProposed scope / conditions\n{item.clearance_conditions}"
    return text.encode("utf-8")
