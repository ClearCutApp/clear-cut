"""`DocumentAIIngestion` against a real Document AI OCR processor.

The proof is `page_start`. The adapter derives it from
`document.pages[].layout.text_anchor.text_segments` (`document_ai.py:59-74`) and
raises `IngestionFailed` when no page carries an anchor, so a scene with a page
number is a scene that came from real OCR over a real PDF. Text alone could come
from anywhere.

`CLEARCUT_LIVE_SCRIPT_GCS_URI` points at a screenplay PDF in the intake bucket.
It is a test input rather than an application setting, so it stays out of
`.env.example` and out of `test_environment_contract.py`'s required set.
"""

import pytest
from google.cloud import documentai_v1 as documentai

from clearcut.adapters.gcp.document_ai import DocumentAIIngestion
from tests.live.conftest import env, requires


@pytest.mark.live
@requires("DOCAI_PROCESSOR_ID", "CLEARCUT_LIVE_SCRIPT_GCS_URI")
def test_parses_a_real_screenplay_into_scenes_with_page_numbers() -> None:
    ingestion = DocumentAIIngestion(
        client=documentai.DocumentProcessorServiceClient(),
        processor_id=env("DOCAI_PROCESSOR_ID"),
    )

    scenes = ingestion.parse(env("CLEARCUT_LIVE_SCRIPT_GCS_URI"), "live-script")

    assert scenes, "a screenplay PDF should yield at least one slugline"
    first = scenes[0]
    assert first.heading.startswith(("INT.", "EXT.")), first.heading
    assert first.page_start >= 1, (
        "page numbers come only from real OCR text anchors; a response without "
        "them raises IngestionFailed rather than reaching here"
    )
    assert first.page_end >= first.page_start
    assert all(later.number > earlier.number for earlier, later in zip(scenes, scenes[1:])), (
        "scene numbers must strictly increase in document order"
    )
