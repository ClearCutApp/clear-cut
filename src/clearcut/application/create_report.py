"""Capture one committed revision and effective human clearance snapshot."""

import hashlib
import json
from dataclasses import asdict
from typing import Any

from clearcut.application.analysis_documents import tracker_data
from clearcut.application.document_ports import ProjectDocuments
from clearcut.application.draft_ports import DraftStore
from clearcut.application.durable_ports import AnalysisArtifacts, ClearanceSnapshots, DurableJobs
from clearcut.application.local_research_ports import LocalResearchStore
from clearcut.application.report_ports import ReportRenderer, ReportStore
from clearcut.domain.report import ClearanceReport, ReportConflict, clearance_counts


class CreateReport:
    def __init__(
        self,
        jobs: DurableJobs,
        snapshots: ClearanceSnapshots,
        artifacts: AnalysisArtifacts,
        reports: ReportStore,
        renderer: ReportRenderer,
        drafts: DraftStore,
        documents: ProjectDocuments,
        local_research: LocalResearchStore | None = None,
    ) -> None:
        self.jobs, self.snapshots, self.artifacts = jobs, snapshots, artifacts
        self.reports, self.renderer, self.drafts = reports, renderer, drafts
        self.documents = documents
        self.local_research = local_research

    def execute(
        self,
        *,
        project_id: str,
        organization_id: str,
        project_title: str,
        analysis_id: str,
        revision_id: str,
        expected_generation: str,
        expected_epoch: int,
        report_id: str,
        actor: str,
        at: str,
        language: str,
    ) -> ClearanceReport:
        if language not in {"en", "es"}:
            raise ValueError("report language must be en or es")
        job = self.jobs.get(project_id, analysis_id)
        baseline, items = self.snapshots.snapshot(project_id)
        if (
            job.state != "SUCCEEDED"
            or job.request.organization_id != organization_id
            or job.request.revision_id != revision_id
            or job.generation_id != baseline.generation_id
            or baseline.generation_id != expected_generation
            or baseline.epoch != expected_epoch
            or job.result is None
            or job.result != baseline.manifest
        ):
            raise ReportConflict("analysis or clearance snapshot changed")
        manifest = self.artifacts.get(job.result)
        if manifest.get("analysis_id") != analysis_id or manifest.get("revision_id") != revision_id:
            raise ReportConflict("analysis manifest does not match requested revision")
        bindings = manifest.get("clearance_bindings", {})
        analyzed_context = json.loads(job.request.production_context_json)
        analyzed_context.pop("analysis_jurisdiction", None)
        counts = clearance_counts(items, bindings)
        draft = self.drafts.get_draft(project_id)
        evidence = [
            asdict(self.documents.metadata(project_id, file_id))
            for file_id in sorted({file_id for item in items for file_id in item.evidence_file_ids})
        ]
        local = self.local_research.capture(project_id) if self.local_research else None
        if local and local.production_context_json != baseline.production_context_json:
            raise ReportConflict("production settings changed while capturing research")
        research_records = []
        for record in local.records if local else []:
            value = dict(record)
            if hasattr(value.get("created_at"), "isoformat"):
                value["created_at"] = value["created_at"].isoformat()
            research_records.append(value)
        research_hash = hashlib.sha256(
            json.dumps(research_records, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        current_context = json.loads(baseline.production_context_json)
        location_coverage = []
        for location in current_context.get("locations", []):
            matching = [
                record["research_id"]
                for record in research_records
                if record.get("location") == location
                and local is not None
                and record.get("settings_version") == local.settings_version
                and record.get("status") == "evidence_found"
                and record.get("citations")
            ]
            location_coverage.append(
                {
                    "location": location,
                    "research_ids": matching,
                    "status": "evidence_recorded" if matching else "coverage_gap",
                }
            )
        context_hash = hashlib.sha256(baseline.production_context_json.encode()).hexdigest()
        snapshot: dict[str, Any] = {
            "schema_version": 1,
            "report_id": report_id,
            "project_id": project_id,
            "organization_id": organization_id,
            "project_title": project_title,
            "analysis_id": analysis_id,
            "revision_id": revision_id,
            "revision_content": asdict(job.request.revision_content),
            "analysis_manifest": asdict(job.result),
            "generation_id": baseline.generation_id,
            "clearance_epoch": baseline.epoch,
            "created_by": actor,
            "created_at": at,
            "language": language,
            "counts": counts,
            "formula_version": "clearance-counts-v1",
            "template_version": "clearance-report-v2",
            "local_research": research_records,
            "local_research_sha256": research_hash,
            "local_research_history_window": local.history_window if local else 0,
            "local_research_epoch": local.epoch if local else None,
            "location_coverage": location_coverage,
            "production_context": job.request.production_context_json,
            "production_context_at_capture": baseline.production_context_json,
            "production_context_changed_at_capture": analyzed_context
            != json.loads(baseline.production_context_json),
            "draft_version_at_capture": draft.version if draft else None,
            "draft_newer_at_capture": bool(draft and draft.version > job.request.revision_version),
            "tracker_items": [tracker_data(item) for item in items],
            "clearance_bindings": bindings,
            "findings": manifest.get("findings", []),
            "scene_anchors": manifest.get("scene_anchors", []),
            "coverage_gaps": manifest.get("coverage_gaps", []),
            "evidence": evidence,
        }
        reference = self.artifacts.put(
            organization_id, project_id, analysis_id, "report-snapshot", snapshot
        )
        pdf = self.artifacts.put_bytes(
            organization_id,
            project_id,
            analysis_id,
            "report-pdf",
            self.renderer.pdf(snapshot),
            "application/pdf",
        )
        csv = self.artifacts.put_bytes(
            organization_id,
            project_id,
            analysis_id,
            "report-csv",
            self.renderer.csv(snapshot),
            "text/csv",
        )
        report = ClearanceReport(
            report_id,
            project_id,
            organization_id,
            analysis_id,
            revision_id,
            baseline.generation_id,
            baseline.epoch,
            actor,
            at,
            language,
            reference,
            pdf,
            csv,
            job.result,
            counts,
            template_version="clearance-report-v2",
            production_context_sha256=context_hash,
            local_research_epoch=local.epoch if local else None,
            settings_version=local.settings_version if local else None,
        )
        self.reports.publish(report)
        return report
