"""Bounded, entity-safe screenplay import with explicit layout interpretation."""

import re
from io import BytesIO
from typing import Any
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from clearcut.application.ports import ScriptIngestion
from clearcut.domain.document import InvalidDocument
from clearcut.domain.screenplay import encode_document

_SLUG = re.compile(r"^(?:INT\.|EXT\.|INT\./EXT\.|EXT\./INT\.)\s", re.IGNORECASE)
_TYPES = {
    "scene heading": "scene-heading",
    "action": "action",
    "character": "character",
    "dialogue": "dialogue",
    "parenthetical": "parenthetical",
    "transition": "transition",
}
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _document(paragraphs: list[tuple[str, str]]) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    scene_id = ""
    for text, kind in paragraphs:
        text = text.strip()
        if not text:
            continue
        if not blocks or kind == "scene-heading" or _SLUG.match(text):
            kind = "scene-heading"
            scene_id = str(uuid4())
        blocks.append(
            {
                "type": "paragraph",
                "attrs": {"blockId": str(uuid4()), "sceneId": scene_id, "kind": kind},
                "content": [{"type": "text", "text": text}],
            }
        )
    if not blocks:
        raise InvalidDocument("no screenplay text found")
    document: dict[str, Any] = {"type": "doc", "content": blocks}
    encode_document(document)
    return document


class ScreenplayImporter:
    def __init__(self, ocr: ScriptIngestion | None = None) -> None:
        self._ocr = ocr

    def parse(
        self, filename: str, data: bytes, original_uri: str, file_id: str
    ) -> tuple[dict[str, Any], list[str]]:
        extension = filename.rsplit(".", 1)[-1].lower()
        try:
            if extension == "fdx":
                root = ElementTree.fromstring(data, forbid_dtd=True)
                if root.tag != "FinalDraft":
                    raise InvalidDocument("file is not a Final Draft screenplay")
                paragraphs = [
                    (
                        "".join(node.itertext()),
                        _TYPES.get(node.get("Type", "Action").lower(), "action"),
                    )
                    for node in root.findall("./Content/Paragraph")
                ]
                return _document(paragraphs), []
            if extension == "docx":
                with ZipFile(BytesIO(data)) as archive:
                    if (
                        len(archive.infolist()) > 1000
                        or sum(item.file_size for item in archive.infolist()) > 20 * 1024 * 1024
                    ):
                        raise InvalidDocument(
                            "Word document expands beyond the 20 MiB import limit"
                        )
                    root = ElementTree.fromstring(
                        archive.read("word/document.xml"), forbid_dtd=True
                    )
                paragraphs = []
                for paragraph in root.findall(f".//{_W}body//{_W}p"):
                    style = paragraph.find(f"{_W}pPr/{_W}pStyle")
                    name = style.get(_W + "val", "") if style is not None else ""
                    name = " ".join(re.sub(r"(?<!^)(?=[A-Z])", " ", name).lower().split())
                    text = "".join(node.text or "" for node in paragraph.iter(_W + "t"))
                    paragraphs.append((text, _TYPES.get(name, "action")))
                return _document(paragraphs), [
                    "Review imported paragraph formatting before saving a revision."
                ]
            if extension == "pdf":
                reader = PdfReader(BytesIO(data), strict=True)
                if reader.is_encrypted:
                    raise InvalidDocument("remove PDF password protection before importing")
                if len(reader.pages) > 300:
                    raise InvalidDocument("PDF exceeds the 300 page import limit")
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
                if not text.strip() and self._ocr is not None:
                    scenes = self._ocr.parse(original_uri, file_id)
                    text = "\n".join(scene.text for scene in scenes)
                if not text.strip():
                    raise InvalidDocument(
                        "PDF has no readable text; OCR is unavailable in this environment"
                    )
                return _document([(line, "action") for line in text.splitlines()]), [
                    "PDF text was imported. Review scene headings and dialogue "
                    "formatting before saving a revision."
                ]
        except InvalidDocument:
            raise
        except (
            DefusedXmlException,
            ElementTree.ParseError,
            BadZipFile,
            KeyError,
            PdfReadError,
            ValueError,
        ) as exc:
            raise InvalidDocument("file could not be parsed as a supported screenplay") from exc
        raise InvalidDocument("import a PDF, DOCX or Final Draft FDX file")
