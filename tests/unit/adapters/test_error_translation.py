"""Proves every adapter error is catchable as its D23 domain type (CP-034,
AGENT.md Section 2 rule 3, CHECKPOINTS.md Decision D23).

Each of the thirteen adapter errors keeps its own module, its own name, and its
own message -- D23 only changes the *type* that crosses the port, from an
adapter-local `Exception` subclass to a `clearcut.domain.errors` subclass.
Each test below raises the adapter's own error and catches it by the domain
type alone, so every binding is proven by behavior rather than by reading the
class statement.
"""

import pytest

from clearcut.adapters.bigquery.lore_store import LoreUnavailable
from clearcut.adapters.clickhouse.client import ClickHouseUnavailable
from clearcut.adapters.clickhouse.tracker import TrackerItemNotFound
from clearcut.adapters.gcp.document_ai import IngestionFailed, NoScenesFound
from clearcut.adapters.gcp.vertex_search import NoGroundedSource
from clearcut.adapters.gemini.continuity import ContinuityCheckFailed
from clearcut.adapters.gemini.extractor import ExtractionFailed
from clearcut.adapters.notify.webhook import NotificationFailed
from clearcut.adapters.parallel.research import NoRightsHolderFound, ResearchUnavailable
from clearcut.adapters.parallel.search import NoWebEvidence, WebSearchUnavailable
from clearcut.domain.errors import EnrichmentMissing, RecordNotFound, SourceUnavailable


def test_tracker_item_not_found_is_a_record_not_found() -> None:
    with pytest.raises(RecordNotFound):
        raise TrackerItemNotFound("prj-1", "EVT-001")


def test_no_grounded_source_is_an_enrichment_missing() -> None:
    with pytest.raises(EnrichmentMissing):
        raise NoGroundedSource("who owns the mural?")


def test_no_rights_holder_found_is_an_enrichment_missing() -> None:
    with pytest.raises(EnrichmentMissing):
        raise NoRightsHolderFound("the mural")


def test_no_web_evidence_is_an_enrichment_missing() -> None:
    with pytest.raises(EnrichmentMissing):
        raise NoWebEvidence("can we show the mural?")


def test_tracker_unavailable_is_a_source_unavailable() -> None:
    with pytest.raises(SourceUnavailable):
        raise ClickHouseUnavailable("failed to save 1 item(s): boom")


def test_lore_unavailable_is_a_source_unavailable() -> None:
    with pytest.raises(SourceUnavailable):
        raise LoreUnavailable("failed to index 1 record(s): boom")


def test_ingestion_failed_is_a_source_unavailable() -> None:
    with pytest.raises(SourceUnavailable):
        raise IngestionFailed("projects/x/processors/y")


def test_no_scenes_found_is_a_source_unavailable() -> None:
    with pytest.raises(SourceUnavailable):
        raise NoScenesFound("script-1")


def test_extraction_failed_is_a_source_unavailable() -> None:
    with pytest.raises(SourceUnavailable):
        raise ExtractionFailed("BOGUS_LABEL")


def test_research_unavailable_is_a_source_unavailable() -> None:
    with pytest.raises(SourceUnavailable):
        raise ResearchUnavailable("Parallel Task API responded with status 503", status_code=503)


def test_web_search_unavailable_is_a_source_unavailable() -> None:
    with pytest.raises(SourceUnavailable):
        raise WebSearchUnavailable("Parallel Search API responded with status 503", status_code=503)


def test_continuity_check_failed_is_a_source_unavailable() -> None:
    with pytest.raises(SourceUnavailable):
        raise ContinuityCheckFailed("BOGUS_CATEGORY")


def test_notification_failed_is_a_source_unavailable() -> None:
    with pytest.raises(SourceUnavailable):
        raise NotificationFailed("webhook responded with status 500", status_code=500)


def test_tracker_item_not_found_message_still_names_the_item_id() -> None:
    try:
        raise TrackerItemNotFound("prj-1", "EVT-042")
    except RecordNotFound as error:
        assert "EVT-042" in str(error)
    else:
        pytest.fail("TrackerItemNotFound was not caught as RecordNotFound")


# `NotificationFailed` and `ResearchUnavailable` assemble their non-2xx
# message at the adapter's raise site, not in their own constructor (CP-035)
# -- unlike `TrackerItemNotFound` above, whose constructor still formats the
# message from a bare id. A test here that raises `NotificationFailed` with a
# hand-written message and then asserts the status code is in that same
# message would only prove the literal string it just supplied. That
# coverage lives instead in
# `test_webhook_notifier.py::test_non_2xx_response_raises_notification_failed_with_status_code`
# and `test_research.py::test_non_2xx_response_raises_research_unavailable_with_status_code`,
# which assert against the adapter's own f-string.
