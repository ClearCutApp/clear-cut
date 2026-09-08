"""Report metadata becomes visible only after snapshot and access revalidation."""

import hashlib
from dataclasses import asdict
from typing import Any

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from clearcut.application.analysis_documents import read_job
from clearcut.domain.activity import activity_envelope
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.identity import AccessDenied, project_permits
from clearcut.domain.report import ClearanceReport, ReportConflict
from clearcut.domain.screenplay import ContentReference


def read_report(data: dict[str, Any]) -> ClearanceReport:
    return ClearanceReport(
        **{
            **data,
            **{
                name: ContentReference(**data[name])
                for name in ("snapshot", "pdf", "csv", "analysis_manifest")
            },
        }
    )


class FirestoreReports:
    def __init__(self, client: Any) -> None:
        self.client = client

    def _project(self, project_id: str) -> Any:
        return self.client.collection("project_access").document(project_id)

    def publish(self, report: ClearanceReport) -> None:
        project_ref = self._project(report.project_id)
        ref = project_ref.collection("reports").document(report.report_id)

        @firestore.transactional
        def write(transaction: Any) -> None:
            project = project_ref.get(transaction=transaction).to_dict() or {}
            member = (
                self.client.collection("organizations")
                .document(report.organization_id)
                .collection("members")
                .document(report.created_by)
                .get(transaction=transaction)
                .to_dict()
                or {}
            )
            job_data = (
                self.client.collection("analysis_jobs")
                .document(report.analysis_id)
                .get(transaction=transaction)
                .to_dict()
            )
            existing = ref.get(transaction=transaction).to_dict()
            if project.get("organization_id") != report.organization_id or not project_permits(
                project, member, report.created_by, "produce"
            ):
                raise AccessDenied("report creation requires project producer access")
            if existing:
                if existing != asdict(report):
                    raise ReportConflict("report identity already published")
                return
            if not job_data:
                raise ReportConflict("analysis no longer available")
            job = read_job(job_data)
            if (
                (
                    report.production_context_sha256
                    and hashlib.sha256(
                        project.get("production_context_json", "{}").encode()
                    ).hexdigest()
                    != report.production_context_sha256
                )
                or (
                    report.local_research_epoch is not None
                    and int(project.get("local_research_epoch", 0)) != report.local_research_epoch
                )
                or (
                    report.settings_version is not None
                    and int(project.get("settings_version", 1)) != report.settings_version
                )
                or project.get("active_generation") != report.generation_id
                or int(project.get("clearance_epoch", 0)) != report.clearance_epoch
                or project.get("committed_analysis_id") != report.analysis_id
                or job.state != "SUCCEEDED"
                or job.request.revision_id != report.revision_id
                or job.request.organization_id != report.organization_id
                or job.request.project_id != report.project_id
                or job.generation_id != report.generation_id
                or job.result != report.analysis_manifest
                or project.get("analysis_manifest") != asdict(report.analysis_manifest)
            ):
                raise ReportConflict("analysis or clearance snapshot changed")
            transaction.create(ref, asdict(report))
            event_id = "report-" + report.report_id
            payload = {
                "report_id": report.report_id,
                "analysis_id": report.analysis_id,
                "revision_id": report.revision_id,
                "counts": report.counts,
                "formula_version": report.formula_version,
            }
            transaction.create(
                self.client.collection("outbox").document(event_id),
                activity_envelope(
                    event_id,
                    report.organization_id,
                    report.project_id,
                    "report_created",
                    report.created_at,
                    report.clearance_epoch,
                    payload,
                ),
            )

        write(self.client.transaction())

    def get(self, project_id: str, report_id: str) -> ClearanceReport:
        data = self._project(project_id).collection("reports").document(report_id).get().to_dict()
        if not data or data.get("project_id") != project_id:
            raise RecordNotFound("report not found")
        return read_report(data)

    def list(self, project_id: str, before: str | None = None) -> list[ClearanceReport]:
        query = self._project(project_id).collection("reports")
        if before:
            query = query.where(filter=FieldFilter("created_at", "<", before))
        return [
            read_report(row.to_dict())
            for row in query.order_by("created_at", direction="DESCENDING").limit(50).stream()
        ]
