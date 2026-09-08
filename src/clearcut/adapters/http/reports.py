"""Private fixed-snapshot report creation, listing and immutable downloads."""

from collections.abc import Callable
from datetime import UTC, datetime
from io import BytesIO
from typing import Any

from flask import Blueprint, Response, g, request, send_file
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import errors, schemas, validators
from clearcut.application.create_report import CreateReport
from clearcut.application.durable_ports import AnalysisArtifacts, ClearanceSnapshots
from clearcut.application.report_ports import ReportStore
from clearcut.domain.report import ClearanceReport, clearance_counts

TAG = "Reports"
TAG_DESCRIPTION = "Immutable private clearance snapshots and PDF/CSV exports."
SCHEMAS: dict[str, Any] = {
    "ClearanceReport": {
        "type": "object",
        "required": [
            "report_id",
            "analysis_id",
            "revision_id",
            "generation_id",
            "clearance_epoch",
            "created_at",
            "counts",
        ],
        "properties": {
            **{
                name: {"type": "string"}
                for name in (
                    "report_id",
                    "project_id",
                    "analysis_id",
                    "revision_id",
                    "generation_id",
                    "created_at",
                    "created_by",
                    "language",
                    "formula_version",
                    "template_version",
                )
            },
            "clearance_epoch": {"type": "integer"},
            "counts": {"type": "object"},
        },
    },
}
PATHS: dict[str, Any] = {
    "/api/projects/{project_id}/reports": {
        "parameters": [schemas.PROJECT_ID],
        "get": {
            "tags": [TAG],
            "operationId": "listReports",
            "responses": {
                "200": schemas.ok(
                    "Saved reports, newest first.", schemas.json_of({"type": "object"})
                )
            },
        },
        "post": {
            "tags": [TAG],
            "operationId": "createReport",
            "requestBody": schemas.body(
                {
                    "type": "object",
                    "required": [
                        "analysis_id",
                        "revision_id",
                        "expected_generation",
                        "expected_epoch",
                        "language",
                    ],
                    "properties": {
                        **{
                            name: {"type": "string"}
                            for name in ("analysis_id", "revision_id", "expected_generation")
                        },
                        "expected_epoch": {"type": "integer", "minimum": 0},
                        "language": {"type": "string", "enum": ["en", "es"]},
                    },
                }
            ),
            "responses": {
                "201": schemas.ok(
                    "Fixed report published.", schemas.json_of(schemas.ref("ClearanceReport"))
                ),
                "409": schemas.ok(
                    "Clearance snapshot changed.", schemas.json_of({"type": "object"})
                ),
            },
        },
    },
    "/api/projects/{project_id}/reports/context": {
        "parameters": [schemas.PROJECT_ID],
        "get": {
            "tags": [TAG],
            "operationId": "getReportContext",
            "responses": {
                "200": schemas.ok(
                    "Current committed snapshot selection.", schemas.json_of({"type": "object"})
                )
            },
        },
    },
    "/api/projects/{project_id}/reports/{report_id}/download": {
        "parameters": [
            schemas.PROJECT_ID,
            {"name": "report_id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        "get": {
            "tags": [TAG],
            "operationId": "downloadReport",
            "parameters": [
                {
                    "name": "format",
                    "in": "query",
                    "schema": {"type": "string", "enum": ["pdf", "csv"]},
                }
            ],
            "responses": {
                "200": {
                    "description": "The immutable saved PDF or CSV bytes.",
                    "content": {
                        "application/pdf": {"schema": {"type": "string", "format": "binary"}},
                        "text/csv": {"schema": {"type": "string", "format": "binary"}},
                    },
                },
                "404": schemas.NOT_FOUND,
            },
        },
    },
}


def report_json(report: ClearanceReport) -> dict[str, Any]:
    return {
        name: getattr(report, name)
        for name in (
            "report_id",
            "project_id",
            "analysis_id",
            "revision_id",
            "generation_id",
            "clearance_epoch",
            "created_by",
            "created_at",
            "language",
            "counts",
            "formula_version",
            "template_version",
        )
    }


def create_reports_blueprint(
    reports: ReportStore | None,
    create: CreateReport | None,
    snapshots: ClearanceSnapshots | None,
    artifacts: AnalysisArtifacts | None,
    project_title: Callable[[str], str],
) -> Blueprint:
    bp = Blueprint("clearcut_reports", __name__)

    @bp.get("/api/projects/<project_id>/reports")
    def index(project_id: str) -> ResponseReturnValue:
        def build() -> dict[str, Any]:
            values = reports.list(project_id, request.args.get("before")) if reports else []
            return {
                "reports": [report_json(value) for value in values],
                "next_before": values[-1].created_at if len(values) == 50 else None,
            }

        return errors.run_use_case(build)

    @bp.get("/api/projects/<project_id>/reports/context")
    def context(project_id: str) -> ResponseReturnValue:
        def build() -> dict[str, Any]:
            if snapshots is None or artifacts is None:
                return {"configured": False, "snapshot": None}
            baseline, items = snapshots.snapshot(project_id)
            if baseline.manifest is None:
                return {"configured": True, "snapshot": None}
            manifest = artifacts.get(baseline.manifest)
            return {
                "configured": True,
                "snapshot": {
                    "analysis_id": manifest["analysis_id"],
                    "revision_id": manifest["revision_id"],
                    "expected_generation": baseline.generation_id,
                    "expected_epoch": baseline.epoch,
                    "counts": clearance_counts(items, manifest.get("clearance_bindings", {})),
                },
            }

        return errors.run_use_case(build)

    @bp.post("/api/projects/<project_id>/reports")
    def publish(project_id: str) -> ResponseReturnValue:
        if create is None:
            return errors.error_response(409, "fixed reports require a committed revision analysis")
        payload = validators.json_body()
        for name in ("analysis_id", "revision_id", "expected_generation", "language"):
            if not isinstance(payload.get(name), str) or not payload[name]:
                return errors.error_response(400, f"{name} is required")
        epoch = payload.get("expected_epoch")
        if payload["language"] not in {"en", "es"}:
            return errors.error_response(400, "report language must be en or es")
        if type(epoch) is not int or epoch < 0:
            return errors.error_response(400, "expected_epoch must be a nonnegative integer")

        def build() -> dict[str, Any]:
            return report_json(
                create.execute(
                    project_id=project_id,
                    organization_id=g.organization_id,
                    project_title=project_title(project_id),
                    analysis_id=payload["analysis_id"],
                    revision_id=payload["revision_id"],
                    expected_generation=payload["expected_generation"],
                    expected_epoch=epoch,
                    report_id=validators.new_id(),
                    actor=g.identity.user_id,
                    at=datetime.now(UTC).isoformat(),
                    language=payload["language"],
                )
            )

        return errors.run_use_case(build, status=201)

    @bp.get("/api/projects/<project_id>/reports/<report_id>/download")
    def download(project_id: str, report_id: str) -> ResponseReturnValue:
        if reports is None or artifacts is None:
            return errors.error_response(404, "report not found")
        format_name = request.args.get("format", "pdf")
        if format_name not in {"pdf", "csv"}:
            return errors.error_response(400, "report format must be pdf or csv")

        def build() -> Response:
            report = reports.get(project_id, report_id)
            content = artifacts.get_bytes(report.pdf if format_name == "pdf" else report.csv)
            response = send_file(
                BytesIO(content),
                mimetype="application/pdf" if format_name == "pdf" else "text/csv",
                as_attachment=True,
                download_name=f"clearance-report-{report_id}.{format_name}",
            )
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response

        return errors.run_use_case(build)

    return bp
