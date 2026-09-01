"""Turns a Document AI response into `Scene`s with page anchors (CP-006).

`DocumentAIIngestion` implements `ScriptIngestion` (docs/plan/sdd.md Section 3).
Scenes are split on recognized sluglines (`INT.`, `EXT.`, `INT./EXT.`) found in
the flat OCR text; each scene's page range comes from overlapping that scene's
character span against every page's own text anchor, so a scene that straddles
a page break carries the full anchor range rather than only its first page.
"""

import re
import time
from typing import Protocol

from google.api_core.exceptions import GoogleAPIError
from google.cloud import documentai_v1 as documentai
from opentelemetry import metrics, trace

from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.script import Scene

_SLUGLINE = re.compile(r"^(?:INT\.|EXT\.)(?:/(?:INT|EXT)\.)?[ \t]", re.MULTILINE)


def _record_stage(stage: str, start: float) -> None:
    """CP-031 (ADR 0008, SDD Section 6): `trace.get_tracer` / `metrics.get_meter`
    are looked up fresh on every call, not cached at import time -- a
    module-level proxy resolved before `composition.py` installs the real
    providers caches that first resolution permanently."""
    duration_ms = (time.perf_counter() - start) * 1000
    metrics.get_meter(__name__).create_histogram(
        "clearcut_stage_latency_ms", unit="ms", description="Pipeline stage latency"
    ).record(duration_ms, {"stage": stage})


class NoScenesFound(SourceUnavailable):
    """Raised when Document AI returned text with no recognizable slugline."""

    def __init__(self, script_id: str) -> None:
        super().__init__(f"no scenes found for script {script_id!r}")
        self.script_id = script_id


class IngestionFailed(SourceUnavailable):
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
    """`(page_number, start_index, end_index)` for each page with a text anchor.

    A page whose `text_segments` is empty carries no position data of its
    own — a blank or image-only page, ordinary in a scanned screenplay — so
    it is skipped instead of crashing `min()`/`max()` on nothing (CP-016).
    """
    spans = []
    for page in document.pages:
        segments = page.layout.text_anchor.text_segments
        if not segments:
            continue
        start = min(int(segment.start_index) for segment in segments)
        end = max(int(segment.end_index) for segment in segments)
        spans.append((page.page_number, start, end))
    return spans


def _pages_overlapping(spans: list[tuple[int, int, int]], start: int, end: int) -> list[int]:
    return [
        number for number, span_start, span_end in spans if span_start < end and span_end > start
    ]


def _nearest_page(spans: list[tuple[int, int, int]], start: int, end: int) -> int:
    """The page whose span is closest to a scene that overlaps none (CP-016).

    `spans` is never empty here: `parse` already raises before calling this
    when no page carries any text.
    """

    def distance(span: tuple[int, int, int]) -> int:
        _, span_start, span_end = span
        if end <= span_start:
            return span_start - end
        if start >= span_end:
            return start - span_end
        return 0

    return min(spans, key=distance)[0]


class DocumentAIIngestion:
    """`ScriptIngestion` backed by a Document AI OCR processor."""

    def __init__(self, client: _DocumentProcessorClient, processor_id: str) -> None:
        self._client = client
        self._processor_id = processor_id

    def parse(self, gcs_uri: str, script_id: str) -> list[Scene]:
        stage_start = time.perf_counter()
        with trace.get_tracer(__name__).start_as_current_span("ingest") as span:
            span.set_attribute("script_id", script_id)
            document = self._process(gcs_uri)
            starts = [match.start() for match in _SLUGLINE.finditer(document.text)]
            if not starts:
                raise NoScenesFound(script_id)
            spans = _page_spans(document)
            if not spans:
                raise IngestionFailed(self._processor_id)
            boundaries = [*starts, len(document.text)]
            scenes = [
                self._scene(number, document.text[start:end], spans, start, end)
                for number, (start, end) in enumerate(zip(boundaries, boundaries[1:]), start=1)
            ]
        _record_stage("ingest", stage_start)
        return scenes

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
        if not pages:
            pages = [_nearest_page(spans, start, end)]
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
