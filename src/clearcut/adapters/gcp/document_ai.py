"""Turns a Document AI response into `Scene`s with page anchors (CP-006).

`DocumentAIIngestion` implements `ScriptIngestion` (docs/plan/sdd.md Section 3).
Scenes are split on recognized sluglines (`INT.`, `EXT.`, `INT./EXT.`) found in
the flat OCR text; each scene's page range comes from overlapping that scene's
character span against every page's own text anchor, so a scene that straddles
a page break carries the full anchor range rather than only its first page.
"""

import re
from typing import Protocol

from google.api_core.exceptions import GoogleAPIError
from google.cloud import documentai_v1 as documentai

from clearcut.domain.script import Scene

_SLUGLINE = re.compile(r"^(?:INT\.|EXT\.)(?:/(?:INT|EXT)\.)?[ \t]", re.MULTILINE)


class NoScenesFound(Exception):
    """Raised when Document AI returned text with no recognizable slugline."""

    def __init__(self, script_id: str) -> None:
        super().__init__(f"no scenes found for script {script_id!r}")
        self.script_id = script_id


class IngestionFailed(Exception):
    """Raised when the Document AI call itself fails, carrying the processor id."""

    def __init__(self, processor_id: str) -> None:
        super().__init__(f"Document AI ingestion failed for processor {processor_id!r}")
        self.processor_id = processor_id


class _DocumentProcessorClient(Protocol):
    """The one Document AI client method this adapter calls (a real I/O boundary)."""

    def process_document(
        self, request: documentai.ProcessRequest
    ) -> documentai.ProcessResponse: ...


def _page_spans(document: documentai.Document) -> list[tuple[int, int, int]]:
    """`(page_number, start_index, end_index)` for each page's own text anchor."""
    spans = []
    for page in document.pages:
        segments = page.layout.text_anchor.text_segments
        start = min(int(segment.start_index) for segment in segments)
        end = max(int(segment.end_index) for segment in segments)
        spans.append((page.page_number, start, end))
    return spans


def _pages_overlapping(spans: list[tuple[int, int, int]], start: int, end: int) -> list[int]:
    return [
        number for number, span_start, span_end in spans if span_start < end and span_end > start
    ]


class DocumentAIIngestion:
    """`ScriptIngestion` backed by a Document AI OCR processor."""

    def __init__(self, client: _DocumentProcessorClient, processor_id: str) -> None:
        self._client = client
        self._processor_id = processor_id

    def parse(self, gcs_uri: str, script_id: str) -> list[Scene]:
        document = self._process(gcs_uri)
        starts = [match.start() for match in _SLUGLINE.finditer(document.text)]
        if not starts:
            raise NoScenesFound(script_id)
        spans = _page_spans(document)
        boundaries = [*starts, len(document.text)]
        return [
            self._scene(number, document.text[start:end], spans, start, end)
            for number, (start, end) in enumerate(zip(boundaries, boundaries[1:]), start=1)
        ]

    def _scene(
        self,
        number: int,
        text: str,
        spans: list[tuple[int, int, int]],
        start: int,
        end: int,
    ) -> Scene:
        heading = text.splitlines()[0].strip()
        pages = _pages_overlapping(spans, start, end)
        return Scene(
            number=number,
            heading=heading,
            page_start=min(pages),
            page_end=max(pages),
            text=text,
        )

    def _process(self, gcs_uri: str) -> documentai.Document:
        request = documentai.ProcessRequest(
            name=self._processor_id,
            gcs_document=documentai.GcsDocument(gcs_uri=gcs_uri, mime_type="application/pdf"),
        )
        try:
            response = self._client.process_document(request=request)
        except GoogleAPIError as error:
            raise IngestionFailed(self._processor_id) from error
        return response.document
