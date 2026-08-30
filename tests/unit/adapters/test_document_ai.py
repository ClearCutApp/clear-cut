"""Unit tests for `DocumentAIIngestion` (CP-006).

The injected client is a hand-written fake (AGENT.md Section 5): no
`unittest.mock`, no network. Fixture responses use the real
`google.cloud.documentai_v1` message types so a shape drift in this adapter's
parsing would fail here rather than against a live processor.
"""

from pathlib import Path
from typing import cast

import pytest
from google.api_core.exceptions import GoogleAPIError, ServiceUnavailable
from google.cloud import documentai_v1 as documentai

from clearcut.adapters.gcp.document_ai import (
    DocumentAIIngestion,
    IngestionFailed,
    NoScenesFound,
)
from clearcut.application.ports import ScriptIngestion

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "docai_three_scenes.json"


class FakeDocumentProcessorClient:
    """Records the request it received; never touches the network."""

    def __init__(
        self,
        document: documentai.Document | None = None,
        error: Exception | None = None,
    ) -> None:
        self._document = document
        self._error = error
        self.requests: list[documentai.ProcessRequest] = []

    def process_document(self, request: documentai.ProcessRequest) -> documentai.ProcessResponse:
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        assert self._document is not None
        return documentai.ProcessResponse(document=self._document)


def _fixture_document() -> documentai.Document:
    # `proto` (proto-plus) ships no py.typed marker, so `from_json` returns Any;
    # `cast` restates the type its own docstring promises without an untyped call.
    response = documentai.ProcessResponse.from_json(FIXTURE_PATH.read_text())
    return cast(documentai.Document, response.document)


def _document_with_text(text: str) -> documentai.Document:
    return documentai.Document(
        text=text,
        pages=[
            documentai.Document.Page(
                page_number=1,
                layout=documentai.Document.Page.Layout(
                    text_anchor=documentai.Document.TextAnchor(
                        text_segments=[
                            documentai.Document.TextAnchor.TextSegment(end_index=len(text))
                        ]
                    )
                ),
            )
        ],
    )


checked: ScriptIngestion = DocumentAIIngestion(
    client=FakeDocumentProcessorClient(),
    processor_id="projects/clearcut-hack/locations/us/processors/dummy",
)


def test_adapter_satisfies_script_ingestion_port() -> None:
    adapter = DocumentAIIngestion(client=FakeDocumentProcessorClient(), processor_id="processor-1")
    assert isinstance(adapter, ScriptIngestion)


def test_parses_three_scenes_split_at_sluglines_from_fixture() -> None:
    client = FakeDocumentProcessorClient(document=_fixture_document())
    adapter = DocumentAIIngestion(client=client, processor_id="processor-1")

    scenes = adapter.parse("gs://clearcut-scripts-intake/script.pdf", "script-1")

    assert len(scenes) == 3
    assert [scene.number for scene in scenes] == [1, 2, 3]
    for scene in scenes:
        assert scene.content_hash != ""


def test_recognizes_int_ext_and_int_slash_ext_sluglines() -> None:
    client = FakeDocumentProcessorClient(document=_fixture_document())
    adapter = DocumentAIIngestion(client=client, processor_id="processor-1")

    scenes = adapter.parse("gs://clearcut-scripts-intake/script.pdf", "script-1")

    assert scenes[0].heading == "INT. APARTMENT - DAY"
    assert scenes[1].heading == "EXT. STREET - NIGHT"
    assert scenes[2].heading == "INT./EXT. CAR - CONTINUOUS"


def test_scene_spanning_a_page_break_returns_the_anchor_range() -> None:
    client = FakeDocumentProcessorClient(document=_fixture_document())
    adapter = DocumentAIIngestion(client=client, processor_id="processor-1")

    scenes = adapter.parse("gs://clearcut-scripts-intake/script.pdf", "script-1")

    street_scene = scenes[1]
    assert street_scene.page_start == 2
    assert street_scene.page_end == 3


def test_scenes_on_a_single_page_have_equal_page_start_and_end() -> None:
    client = FakeDocumentProcessorClient(document=_fixture_document())
    adapter = DocumentAIIngestion(client=client, processor_id="processor-1")

    scenes = adapter.parse("gs://clearcut-scripts-intake/script.pdf", "script-1")

    assert (scenes[0].page_start, scenes[0].page_end) == (1, 1)
    assert (scenes[2].page_start, scenes[2].page_end) == (4, 4)


def test_text_without_a_slugline_raises_no_scenes_found_instead_of_empty_list() -> None:
    document = _document_with_text("FADE IN:\n\nA quiet moment with no scene heading.\n")
    client = FakeDocumentProcessorClient(document=document)
    adapter = DocumentAIIngestion(client=client, processor_id="processor-1")

    with pytest.raises(NoScenesFound):
        adapter.parse("gs://clearcut-scripts-intake/script.pdf", "script-1")


def test_transport_error_is_translated_to_ingestion_failed_carrying_processor_id() -> None:
    # google.api_core's GoogleAPICallError.__init__ carries no type annotations.
    error = ServiceUnavailable("upstream unavailable")  # type: ignore[no-untyped-call]
    client = FakeDocumentProcessorClient(error=error)
    adapter = DocumentAIIngestion(
        client=client, processor_id="projects/clearcut-hack/locations/us/processors/dummy"
    )

    try:
        adapter.parse("gs://clearcut-scripts-intake/script.pdf", "script-1")
    except GoogleAPIError:
        pytest.fail("a google.api_core exception escaped the adapter")
    except IngestionFailed as error:
        assert error.processor_id == "projects/clearcut-hack/locations/us/processors/dummy"
    else:
        pytest.fail("expected IngestionFailed to be raised")


def test_process_request_carries_the_processor_id_the_adapter_was_constructed_with() -> None:
    client = FakeDocumentProcessorClient(document=_fixture_document())
    processor_id = "processor-injected-at-construction"
    adapter = DocumentAIIngestion(client=client, processor_id=processor_id)

    adapter.parse("gs://clearcut-scripts-intake/script.pdf", "script-1")

    assert client.requests[0].name == processor_id


def test_parse_makes_no_network_call() -> None:
    client = FakeDocumentProcessorClient(document=_fixture_document())
    adapter = DocumentAIIngestion(client=client, processor_id="processor-1")

    adapter.parse("gs://clearcut-scripts-intake/script.pdf", "script-1")

    assert len(client.requests) == 1


def test_page_with_empty_text_segments_is_skipped_other_pages_still_parse() -> None:
    # A blank or image-only page in a scanned screenplay carries no text
    # segments at all; it must not crash the pages that do have text (CP-016).
    text = "INT. APARTMENT - DAY\n\nJohn stares at the wall.\n"
    document = documentai.Document(
        text=text,
        pages=[
            documentai.Document.Page(
                page_number=1,
                layout=documentai.Document.Page.Layout(
                    text_anchor=documentai.Document.TextAnchor(
                        text_segments=[
                            documentai.Document.TextAnchor.TextSegment(end_index=len(text))
                        ]
                    )
                ),
            ),
            documentai.Document.Page(
                page_number=2,
                layout=documentai.Document.Page.Layout(
                    text_anchor=documentai.Document.TextAnchor(text_segments=[])
                ),
            ),
        ],
    )
    client = FakeDocumentProcessorClient(document=document)
    adapter = DocumentAIIngestion(client=client, processor_id="processor-1")

    scenes = adapter.parse("gs://clearcut-scripts-intake/script.pdf", "script-1")

    assert len(scenes) == 1
    assert (scenes[0].page_start, scenes[0].page_end) == (1, 1)


def test_response_with_no_pages_raises_ingestion_failed_naming_processor_id() -> None:
    # No page carries any text segment (here: no pages at all), so the
    # adapter cannot place any scene on a page (CP-016).
    text = "INT. APARTMENT - DAY\n\nJohn stares at the wall.\n"
    document = documentai.Document(text=text, pages=[])
    client = FakeDocumentProcessorClient(document=document)
    adapter = DocumentAIIngestion(
        client=client, processor_id="projects/clearcut-hack/locations/us/processors/dummy"
    )

    with pytest.raises(IngestionFailed) as excinfo:
        adapter.parse("gs://clearcut-scripts-intake/script.pdf", "script-1")

    assert excinfo.value.processor_id == "projects/clearcut-hack/locations/us/processors/dummy"


def test_scene_overlapping_no_page_span_falls_back_to_the_nearest_page() -> None:
    # Neither page span overlaps the scene's character range; the fallback
    # picks the page nearest by character distance, not simply the first
    # page in the list (CP-016) — proven by listing the farther page first.
    text = "INT. APARTMENT - DAY\n\nJohn stares at the wall.\n"
    document = documentai.Document(
        text=text,
        pages=[
            documentai.Document.Page(
                page_number=5,
                layout=documentai.Document.Page.Layout(
                    text_anchor=documentai.Document.TextAnchor(
                        text_segments=[
                            documentai.Document.TextAnchor.TextSegment(
                                start_index=200, end_index=250
                            )
                        ]
                    )
                ),
            ),
            documentai.Document.Page(
                page_number=2,
                layout=documentai.Document.Page.Layout(
                    text_anchor=documentai.Document.TextAnchor(
                        text_segments=[
                            documentai.Document.TextAnchor.TextSegment(
                                start_index=100, end_index=150
                            )
                        ]
                    )
                ),
            ),
        ],
    )
    client = FakeDocumentProcessorClient(document=document)
    adapter = DocumentAIIngestion(client=client, processor_id="processor-1")

    scenes = adapter.parse("gs://clearcut-scripts-intake/script.pdf", "script-1")

    assert (scenes[0].page_start, scenes[0].page_end) == (2, 2)
