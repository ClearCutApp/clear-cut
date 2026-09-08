"""Bounded official-source retrieval and reproducible text transformations."""

from __future__ import annotations

import hashlib
import io
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

import httpx
from pypdf import PdfReader

from infra.fetch_legal_corpus import is_official

MAX_BYTES = 64 * 1024 * 1024


class SourceRejected(ValueError):
    """No trustworthy full text was obtained; preserve an explicit coverage gap."""


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def download(http: httpx.Client, url: str) -> tuple[bytes, str, str]:
    for _ in range(6):
        if not is_official(url):
            raise SourceRejected("source or redirect is not an allowed official HTTPS host")
        with http.stream("GET", url, follow_redirects=False) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise SourceRejected("redirect has no location")
                url = urljoin(url, location)
                continue
            if response.status_code != 200:
                raise SourceRejected(f"official source returned HTTP {response.status_code}")
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > MAX_BYTES:
                    raise SourceRejected("official source exceeds 64 MiB")
            return bytes(content), response.headers.get("content-type", ""), url
    raise SourceRejected("official source exceeded five redirects")


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript"):
            self.hidden += 1
        elif tag in ("p", "div", "br", "tr", "li", "h1", "h2", "h3"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript"):
            self.hidden = max(0, self.hidden - 1)
        elif tag in ("p", "div", "tr", "li"):
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def extract(content: bytes, mime: str, source: dict[str, Any]) -> tuple[bytes, str]:
    if not content or len(content) > MAX_BYTES:
        raise SourceRejected("empty or oversized source")
    skip = source.get("skip_pdf_pages", 0)
    if not isinstance(skip, int) or isinstance(skip, bool) or skip < 0:
        raise SourceRejected("invalid PDF transformation")
    if content.startswith(b"%PDF-"):
        if "pdf" not in mime.lower() and "octet-stream" not in mime.lower():
            raise SourceRejected("PDF bytes disagree with response MIME")
        try:
            pdf = PdfReader(io.BytesIO(content))
            if pdf.is_encrypted or not skip < len(pdf.pages) <= 1000:
                raise SourceRejected("encrypted, empty or over-1000-page PDF")
            text = "\n\n".join(page.extract_text() or "" for page in pdf.pages[skip:])
        except SourceRejected:
            raise
        except Exception as exc:
            raise SourceRejected("PDF extraction failed") from exc
        transform = f"pypdf-6.17.0:text;skip-first-pages={skip}"
    elif "html" in mime.lower() and b"<" in content[:1024]:
        if skip:
            raise SourceRejected("PDF-only transformation received HTML")
        charset_match = re.search(r"charset=[\"']?([\w-]+)", mime, re.I)
        if charset_match:
            charset = charset_match.group(1)
        else:
            declared = re.search(rb"charset\s*=\s*[\"']?([\w-]+)", content[:8192], re.I)
            charset = declared.group(1).decode("ascii") if declared else "utf-8-sig"
        try:
            html = content.decode(charset)
        except (UnicodeDecodeError, LookupError):
            raise SourceRejected("HTML encoding is unsupported or inconsistent") from None
        parser = _VisibleText()
        parser.feed(html)
        text = "".join(parser.parts)
        transform = f"html-visible-text-v1:{charset}"
    else:
        raise SourceRejected("source is not a supported full-text PDF or HTML document")
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if len(text) < 500:
        raise SourceRejected("insufficient extracted text; OCR or source review required")
    for marker in source.get("required_text", []):
        if marker.casefold() not in text.casefold():
            raise SourceRejected("required legal text marker missing")
    if source.get("required_pattern") and not re.search(source["required_pattern"], text, re.I):
        raise SourceRejected("required edition marker missing")
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_BYTES:
        raise SourceRejected("extracted text exceeds 64 MiB")
    return encoded, transform
