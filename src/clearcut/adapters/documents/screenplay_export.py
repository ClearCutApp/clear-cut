"""Screenplay downloads rendered from one immutable saved revision."""

from io import BytesIO
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import CondPageBreak, Paragraph, SimpleDocTemplate, Spacer

from clearcut.domain.screenplay import encode_document

_TYPES = {
    "scene-heading": "Scene Heading",
    "action": "Action",
    "character": "Character",
    "dialogue": "Dialogue",
    "parenthetical": "Parenthetical",
    "transition": "Transition",
}


def screenplay_fdx(document: dict[str, Any]) -> bytes:
    encode_document(document)
    root = Element("FinalDraft", {"DocumentType": "Script", "Template": "No", "Version": "1"})
    content = SubElement(root, "Content")
    for block in document["content"]:
        paragraph = SubElement(content, "Paragraph", {"Type": _TYPES[block["attrs"]["kind"]]})
        for node in block.get("content", []):
            text = SubElement(paragraph, "Text")
            text.text = node.get("text", "\n")
            marks = [mark["type"].title() for mark in node.get("marks", [])]
            if marks:
                text.set("Style", "+".join(marks))
    return bytes(tostring(root, encoding="utf-8", xml_declaration=True))


class _AnchoredParagraph(Paragraph):  # type: ignore[misc]
    """ReportLab splits long blocks; retain their identity on every fragment."""

    block_id: str = ""

    def split(self, availWidth: float, availHeight: float) -> list[Any]:
        parts: list[Any] = super().split(availWidth, availHeight)
        for part in parts:
            part.block_id = self.block_id
        return parts


def screenplay_pdf(document: dict[str, Any], title: str, revision_label: str) -> bytes:
    return screenplay_layout(document, title, revision_label)[0]


def screenplay_layout(
    document: dict[str, Any], title: str, revision_label: str
) -> tuple[bytes, dict[str, tuple[int, int]]]:
    encode_document(document)
    output = BytesIO()
    pdf = SimpleDocTemplate(
        output,
        pagesize=(8.5 * inch, 11 * inch),
        leftMargin=1.5 * inch,
        rightMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
        title=title,
        author="",
        pageCompression=1,
    )
    pages: dict[str, tuple[int, int]] = {}

    def record_block(flowable: Any) -> None:
        block_id = getattr(flowable, "block_id", "")
        if block_id:
            first, _ = pages.get(block_id, (pdf.page, pdf.page))
            pages[block_id] = (first, pdf.page)

    pdf.afterFlowable = record_block
    styles = {
        kind: ParagraphStyle(
            kind,
            fontName="Courier-Bold" if kind == "scene-heading" else "Courier",
            fontSize=12,
            leading=12,
            spaceAfter=12 if kind not in {"character", "parenthetical"} else 0,
            leftIndent=(
                1.5 * inch
                if kind == "dialogue"
                else 2 * inch
                if kind in {"character", "parenthetical"}
                else 0
            ),
            rightIndent=inch if kind in {"dialogue", "parenthetical"} else 0,
            alignment=TA_RIGHT if kind == "transition" else TA_LEFT,
            keepWithNext=False,
        )
        for kind in _TYPES
    }
    story: list[Any] = []
    for block in document["content"]:
        if block["attrs"]["kind"] in {"scene-heading", "character", "parenthetical"}:
            story.append(CondPageBreak(36))
        rendered = ""
        for node in block.get("content", []):
            part = (
                escape(node.get("text", "")).replace("\n", "<br/>")
                if node["type"] == "text"
                else "<br/>"
            )
            for mark in node.get("marks", []):
                tag = "b" if mark["type"] == "bold" else "i"
                part = f"<{tag}>{part}</{tag}>"
            rendered += part
        paragraph = _AnchoredParagraph(rendered or "&nbsp;", styles[block["attrs"]["kind"]])
        paragraph.block_id = block["attrs"]["blockId"]
        story.append(paragraph)
    if not story:
        story.append(Spacer(1, 1))

    def footer(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont("Courier", 8)
        canvas.drawString(1.5 * inch, 0.55 * inch, revision_label)
        canvas.drawRightString(7.5 * inch, 0.55 * inch, str(doc.page))
        canvas.restoreState()

    pdf.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue(), pages
