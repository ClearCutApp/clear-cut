"""Tests for the Parallel Task API rights-research adapter (CP-010, SDD Section 3).

The transport is faked at the httpx level (`httpx.MockTransport`), the seam
`parallel.Parallel` itself exposes for injecting a client, rather than
patching the SDK (AGENT.md Section 5).
"""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from clearcut.adapters.parallel.research import (
    NoRightsHolderFound,
    ParallelRightsResearch,
    ResearchUnavailable,
)
from clearcut.application.ports import Confidence, RightsClaim, RightsResearch
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.finding import Category
from clearcut.domain.jurisdiction import jurisdiction_for
from tests.unit.conftest import install_in_memory_telemetry, metric_attributes_by_name

_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "parallel_task_result.json"
_SRC = Path(__file__).resolve().parents[3] / "src" / "clearcut"
_ADAPTER_SOURCE = _SRC / "adapters" / "parallel" / "research.py"
_ASSET_NAME = "Hotel California"
_JURISDICTION = jurisdiction_for("ES")


def _result_body() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text())  # type: ignore[no-any-return]


def _run_body() -> dict[str, Any]:
    return {
        "run_id": "trun_fixture123",
        "status": "queued",
        "is_active": True,
        "processor": "core",
        "interaction_id": "int_fixture123",
    }


def _adapter(
    result_body: dict[str, Any],
    *,
    create_status: int = 200,
    result_status: int = 200,
) -> ParallelRightsResearch:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/tasks/runs":
            return httpx.Response(create_status, json=_run_body())
        return httpx.Response(result_status, json=result_body)

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    return ParallelRightsResearch(http_client, "parallel-test-key")


def test_adapter_implements_rights_research_port() -> None:
    adapter = _adapter(_result_body())
    checked: RightsResearch = adapter
    assert isinstance(checked, RightsResearch)


def test_fixture_task_result_returns_rights_claim_with_expected_fields() -> None:
    adapter = _adapter(_result_body())

    claim = adapter.find(_ASSET_NAME, Category.COPYRIGHT_WORKS, _JURISDICTION)

    assert isinstance(claim, RightsClaim)
    assert claim.holder == "Sony Music Publishing"
    assert claim.contact == "licensing@sonymusicpub.com"
    assert claim.litigation_posture == "No known disputes over similar synchronization uses."
    assert claim.confidence == Confidence.HIGH
    assert len(claim.citations) == 1
    citation = claim.citations[0]
    assert citation.uri == "https://www.ascap.com/repertory#/ace/search/title/Hotel%20California"
    assert citation.title == "ASCAP ACE Repertory"


def test_claim_without_citation_is_dropped_returns_only_the_cited_one() -> None:
    # Swap the order so the uncited claim comes first: a filter that just
    # returned claims[0] would wrongly surface the uncited aggregator here.
    body = copy.deepcopy(_result_body())
    body["output"]["content"]["claims"].reverse()
    for basis, field in zip(body["output"]["basis"], ("claims.1", "claims.0"), strict=True):
        basis["field"] = field
    adapter = _adapter(body)

    claim = adapter.find(_ASSET_NAME, Category.COPYRIGHT_WORKS, _JURISDICTION)

    assert claim.holder == "Sony Music Publishing"


def test_all_claims_uncited_raises_no_rights_holder_found() -> None:
    body = copy.deepcopy(_result_body())
    for basis in body["output"]["basis"]:
        basis["citations"] = []
    adapter = _adapter(body)

    with pytest.raises(NoRightsHolderFound) as excinfo:
        adapter.find(_ASSET_NAME, Category.COPYRIGHT_WORKS, _JURISDICTION)

    assert excinfo.value.asset_name == _ASSET_NAME


def test_non_2xx_response_raises_research_unavailable_with_status_code() -> None:
    adapter = _adapter(_result_body(), create_status=500, result_status=500)

    with pytest.raises(ResearchUnavailable) as excinfo:
        adapter.find(_ASSET_NAME, Category.COPYRIGHT_WORKS, _JURISDICTION)

    assert excinfo.value.status_code == 500
    assert "500" in str(excinfo.value)


def test_unrecognized_confidence_string_maps_to_low_instead_of_raising() -> None:
    # `FieldBasis.confidence` is typed `Optional[str]` by the Parallel SDK, so
    # any string can arrive; an unrecognized one must not raise (CP-016).
    body = copy.deepcopy(_result_body())
    body["output"]["basis"][0]["confidence"] = "probably"
    adapter = _adapter(body)

    claim = adapter.find(_ASSET_NAME, Category.COPYRIGHT_WORKS, _JURISDICTION)

    assert claim.confidence == Confidence.LOW


def _adapter_with_transport_failure(error: httpx.TransportError) -> ParallelRightsResearch:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    return ParallelRightsResearch(http_client, "parallel-test-key")


def test_read_timeout_raises_research_unavailable_with_a_distinct_message() -> None:
    adapter = _adapter_with_transport_failure(httpx.ReadTimeout("timed out"))

    with pytest.raises(ResearchUnavailable) as excinfo:
        adapter.find(_ASSET_NAME, Category.COPYRIGHT_WORKS, _JURISDICTION)

    assert type(excinfo.value) is ResearchUnavailable
    assert "responded with status" not in str(excinfo.value)
    assert excinfo.value.status_code is None
    # `parallel.APITimeoutError`'s own message, which `research.py:104`
    # interpolates in -- pins the message to the underlying error's own text
    # rather than to something the message merely happens not to say (D34).
    assert "Request timed out." in str(excinfo.value)


def test_read_timeout_is_catchable_as_source_unavailable_alone() -> None:
    adapter = _adapter_with_transport_failure(httpx.ReadTimeout("timed out"))

    with pytest.raises(SourceUnavailable):
        adapter.find(_ASSET_NAME, Category.COPYRIGHT_WORKS, _JURISDICTION)


def test_connect_error_message_differs_from_non_2xx_status_message() -> None:
    connect_adapter = _adapter_with_transport_failure(httpx.ConnectError("connection refused"))
    status_adapter = _adapter(_result_body(), create_status=500, result_status=500)

    with pytest.raises(ResearchUnavailable) as connect_excinfo:
        connect_adapter.find(_ASSET_NAME, Category.COPYRIGHT_WORKS, _JURISDICTION)
    with pytest.raises(ResearchUnavailable) as status_excinfo:
        status_adapter.find(_ASSET_NAME, Category.COPYRIGHT_WORKS, _JURISDICTION)

    assert str(connect_excinfo.value) != str(status_excinfo.value)


def test_find_opens_a_research_span_and_records_stage_latency(isolated_otel: None) -> None:
    span_exporter, metric_reader = install_in_memory_telemetry()
    adapter = _adapter(_result_body())

    adapter.find(_ASSET_NAME, Category.COPYRIGHT_WORKS, _JURISDICTION)

    spans = [span for span in span_exporter.get_finished_spans() if span.name == "research"]
    assert len(spans) == 1

    latency_points = metric_attributes_by_name(metric_reader)["clearcut_stage_latency_ms"]
    assert latency_points
    assert all(point["stage"] == "research" for point in latency_points)


def test_module_does_not_import_or_reference_risk_level() -> None:
    source = _ADAPTER_SOURCE.read_text()
    tree = ast.parse(source)
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            imported_names.update(alias.asname or alias.name for alias in node.names)

    assert "RiskLevel" not in imported_names
    assert "risk_level" not in source


# --- CP-056: a 2xx the SDK accepts but cannot use ----------------------------
#
# Written to prove APIResponseValidationError became a 502, and it found
# something nearer to hand instead. The SDK accepts a run-create body of any
# shape, then `task_run.result(None)` raises a bare ValueError from inside the
# SDK, which routes.py maps to 500. Schema drift on a partner API reported to
# the producer as a ClearCut bug is exactly what a partner-track submission
# cannot afford.


def test_a_2xx_run_create_with_no_run_id_becomes_research_unavailable() -> None:
    """The run-create call answers 200 with a body carrying no `run_id`."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/tasks/runs":
            return httpx.Response(200, json={"unexpected": "shape"})
        return httpx.Response(200, json=_result_body())

    adapter = ParallelRightsResearch(
        httpx.Client(transport=httpx.MockTransport(handler)), "parallel-test-key"
    )

    with pytest.raises(SourceUnavailable) as caught:
        adapter.find("Hotel California", Category.COPYRIGHT_WORKS, jurisdiction_for("ES"))

    assert isinstance(caught.value, ResearchUnavailable)
    assert not isinstance(caught.value, ValueError)
