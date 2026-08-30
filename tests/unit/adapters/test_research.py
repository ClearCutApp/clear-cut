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
from clearcut.domain.finding import Category
from clearcut.domain.jurisdiction import jurisdiction_for

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


def test_module_does_not_import_or_reference_risk_level() -> None:
    source = _ADAPTER_SOURCE.read_text()
    tree = ast.parse(source)
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            imported_names.update(alias.asname or alias.name for alias in node.names)

    assert "RiskLevel" not in imported_names
    assert "risk_level" not in source
