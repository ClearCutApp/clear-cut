"""A report freezes effective human overlays and original evidence hashes."""

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace
from typing import Any

import pytest

from clearcut.adapters.demo.documents import MemoryProjectDocuments
from clearcut.adapters.gcp.analysis_jobs import FirestoreAnalysisJobs
from clearcut.application.create_report import CreateReport
from clearcut.domain.durable_analysis import ClearanceSnapshot
from clearcut.domain.report import ReportConflict
from clearcut.domain.screenplay import ContentReference
from tests.unit.adapters.test_clearance_transactions import item
from tests.unit.adapters.test_reports import ready_report
from tests.unit.application.test_analysis_checkpoints import Artifacts


class ReportArtifacts(Artifacts):
    def __init__(self) -> None:
        super().__init__()
        self.bytes: dict[str, bytes] = {}

    def put_bytes(
        self,
        organization_id: str,
        project_id: str,
        analysis_id: str,
        kind: str,
        content: bytes,
        content_type: str,
    ) -> ContentReference:
        key = sha256(content).hexdigest()
        self.bytes[key] = content
        return ContentReference(key, key, len(content))

    def get_bytes(self, reference: ContentReference) -> bytes:
        return self.bytes[reference.uri]


@pytest.mark.parametrize("race", [False, True])
def test_effective_snapshot_and_derivatives_are_frozen_or_remain_unpublished(race):
    client, reports, ready = ready_report()
    artifacts = ReportArtifacts()
    documents = MemoryProjectDocuments()
    evidence = documents.put(
        "org", "project", "release.txt", "text/plain", b"signed", "evidence", "writer", "now"
    )
    current = replace(
        item(), version=4, note="Human overlay", evidence_file_ids=(evidence.file_id,)
    )
    manifest = {
        "analysis_id": "analysis",
        "revision_id": "revision-1",
        "tracker_items": [{"note": "old generated note"}],
        "clearance_bindings": {"asset": {"present": True, "revision_id": "revision-1"}},
    }
    artifacts.values[ready.analysis_manifest.uri] = manifest
    baseline = ClearanceSnapshot("generation", 2, ready.analysis_manifest)

    class Renderer:
        def pdf(self, snapshot: dict[str, Any]) -> bytes:
            if race:
                client.data["project_access/project"]["clearance_epoch"] = 3
            return str(snapshot["tracker_items"][0]["note"]).encode()

        def csv(self, snapshot: dict[str, Any]) -> bytes:
            return str(snapshot["evidence"][0]["sha256"]).encode()

    use_case = CreateReport(
        FirestoreAnalysisJobs(client),
        SimpleNamespace(snapshot=lambda project: (baseline, [current])),
        artifacts,
        reports,
        Renderer(),
        SimpleNamespace(get_draft=lambda project: SimpleNamespace(version=4)),
        documents,
    )
    args: dict[str, Any] = dict(
        project_id="project",
        organization_id="org",
        project_title="Production",
        analysis_id="analysis",
        revision_id="revision-1",
        expected_generation="generation",
        expected_epoch=2,
        report_id="report",
        actor="writer",
        at="now",
        language="es",
    )
    if race:
        with pytest.raises(ReportConflict):
            use_case.execute(**args)
        assert "project_access/project/reports/report" not in client.data
        assert "outbox/report-report" not in client.data
    else:
        result = use_case.execute(**args)
        captured = deepcopy(artifacts.get(result.snapshot))
        assert captured["tracker_items"][0]["version"] == 4
        assert captured["evidence"][0]["sha256"] == sha256(b"signed").hexdigest()
        assert captured["draft_newer_at_capture"] is True
        assert artifacts.get_bytes(result.pdf) == b"Human overlay"
        current = replace(current, note="Later edit", version=5)
        assert artifacts.get(result.snapshot) == captured
        assert reports.get("project", "report") == result


def test_saved_report_freezes_local_evidence_and_marks_unsupported_locations():
    import json
    from unittest.mock import Mock

    from clearcut.application.local_research_ports import LocalResearchSnapshot

    client, reports, ready = ready_report()
    locations = [
        {"country": "AR", "location": "Buenos Aires"},
        {"country": "MX", "location": "CDMX"},
    ]
    context = json.dumps({"locations": locations})
    client.data["project_access/project"].update(
        {"production_context_json": context, "settings_version": 2, "local_research_epoch": 1}
    )
    artifacts = ReportArtifacts()
    artifacts.values[ready.analysis_manifest.uri] = {
        "analysis_id": "analysis",
        "revision_id": "revision-1",
        "clearance_bindings": {},
    }
    records = [
        {
            "research_id": "research",
            "location": locations[0],
            "settings_version": 2,
            "status": "evidence_found",
            "question": "Close this road?",
            "text": "Check the authority.",
            "created_at": "2026-09-06T12:00:00Z",
            "citations": [
                {
                    "uri": "https://buenosaires.gob.ar/rodajes",
                    "title": "Official",
                    "snippet": "Ask the authority.",
                }
            ],
            "human_clearance": False,
        }
    ]
    research = Mock()
    research.capture.return_value = LocalResearchSnapshot(1, 2, context, records)
    renderer = Mock()
    renderer.pdf.return_value = b"pdf"
    renderer.csv.return_value = b"csv"
    use_case = CreateReport(
        FirestoreAnalysisJobs(client),
        SimpleNamespace(
            snapshot=lambda project: (
                ClearanceSnapshot("generation", 2, ready.analysis_manifest, context),
                [item()],
            )
        ),
        artifacts,
        reports,
        renderer,
        SimpleNamespace(get_draft=lambda project: None),
        MemoryProjectDocuments(),
        research,
    )
    report = use_case.execute(
        project_id="project",
        organization_id="org",
        project_title="Film",
        analysis_id="analysis",
        revision_id="revision-1",
        expected_generation="generation",
        expected_epoch=2,
        report_id="report",
        actor="writer",
        at="now",
        language="en",
    )
    saved = deepcopy(artifacts.get(report.snapshot))
    assert saved["location_coverage"][0]["status"] == "evidence_recorded"
    assert saved["location_coverage"][1]["status"] == "coverage_gap"
    assert saved["local_research"][0]["human_clearance"] is False
    assert report.local_research_epoch == 1 and report.settings_version == 2
    assert report.template_version == "clearance-report-v2"
    records[0]["text"] = "Later change"
    assert artifacts.get(report.snapshot) == saved
