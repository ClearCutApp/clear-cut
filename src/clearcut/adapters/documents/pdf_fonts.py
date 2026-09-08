"""Embedded redistributable fonts and visible fallbacks for unsupported glyphs."""

import unicodedata
from pathlib import Path
from threading import Lock

import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

REGULAR = "ClearCutSans"
BOLD = "ClearCutSans-Bold"
_lock = Lock()
_supported: set[int] | None = None


def register() -> None:
    global _supported
    with _lock:
        if _supported is not None:
            return
        root = Path(reportlab.__file__).parent / "fonts"
        regular = TTFont(REGULAR, str(root / "Vera.ttf"))
        bold = TTFont(BOLD, str(root / "VeraBd.ttf"))
        pdfmetrics.registerFont(regular)
        pdfmetrics.registerFont(bold)
        pdfmetrics.registerFontFamily(
            REGULAR, normal=REGULAR, bold=BOLD, italic=REGULAR, boldItalic=BOLD
        )
        _supported = set(regular.face.charToGlyph) & set(bold.face.charToGlyph)


def text(value: object) -> str:
    register()
    assert _supported is not None
    value = unicodedata.normalize("NFC", str(value or ""))
    return "".join(
        character
        if character in "\n\t" or ord(character) in _supported
        else "[" + unicodedata.name(character, f"U+{ord(character):04X}") + "]"
        for character in value
    )
