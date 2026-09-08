"""Scripts: uploads, versions, and the analyses they queue.

`POST .../scripts` answers **202**, not the report (ADR 0013). On real
services the pipeline takes twelve to twenty minutes, and a browser tab, a
load balancer, a corporate proxy and a phone changing networks all give up
long before that without telling the server. The producer gets an analysis id
and polls it, and can close the tab and come back.

`GET .../scripts/{script_id}` is what makes that worth doing. Findings are
persisted now (ADR 0014), so a reload serves the same scenes, findings and
highlight spans the run produced -- before this the evidence existed only in
the body of the response that reported it, and Script Review rendered nothing
after a refresh.

The upload is separate from the analysis on purpose: re-analyzing the same
draft costs no second transfer of a 25 MiB PDF.

`PATHS` and `SCHEMAS` live in `scripts_spec.py`; they are re-exported here so
`openapi.py` reads every domain the same way.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from flask import Blueprint, g, request
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import errors, scripts_spec, serializers, validators
from clearcut.application.draft_ports import DraftStore
from clearcut.application.durable_ports import AnalysisManifestReader, DurableJobs
from clearcut.application.get_analysis import GetAnalysis
from clearcut.application.get_script import GetScript
from clearcut.application.list_scripts import ListScripts
from clearcut.application.start_analysis import StartAnalysis
from clearcut.application.upload_script_file import UploadScriptFile
from clearcut.application.workspace_ports import OwnedFiles
from clearcut.domain.durable_analysis import DurableJob, NewAnalysis
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.jurisdiction import Jurisdiction

JsonDict = dict[str, Any]

TAG = scripts_spec.TAG
TAG_DESCRIPTION = scripts_spec.TAG_DESCRIPTION
PATHS = scripts_spec.PATHS
SCHEMAS = scripts_spec.SCHEMAS

# Cloud Run refuses a request body over 32 MiB, so a larger upload never
# reaches this process at all and could not be answered honestly. The cap
# below sits under that, which makes the 413 ours to return rather than the
# platform's to drop.
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024

_PDF = "application/pdf"

_FILE_FIELD = "file"

_TOO_LARGE = "file is over 25 MiB"


@dataclass(frozen=True)
class _Upload:
    """The one upload this service accepts, once it is known to be usable."""

    filename: str
    content: bytes


def _read_upload() -> _Upload | ResponseReturnValue:
    """The request's `file` part, or the 400/413 naming why it is not usable.

    Type is checked from the part's own content type rather than from the
    filename's extension: the extension is producer-supplied text, and
    Document AI is configured for PDF alone, so a `.pdf` that is really a
    Word file would fail minutes later inside a queued job instead of here.

    The length is checked twice. `Content-Length` rejects an oversized body
    without reading it, and a chunked upload carries no such header, so the
    bytes are measured again once they are in hand.
    """
    uploaded = request.files.get(_FILE_FIELD)
    if uploaded is None:
        return errors.error_response(400, f"{_FILE_FIELD} is required")
    if uploaded.mimetype != _PDF:
        return errors.error_response(400, f"{_FILE_FIELD} must be a PDF, got {uploaded.mimetype}")
    declared = request.content_length
    if declared is not None and declared > _MAX_UPLOAD_BYTES:
        return errors.error_response(413, _TOO_LARGE)
    content = uploaded.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        return errors.error_response(413, _TOO_LARGE)
    return _Upload(filename=uploaded.filename or "script.pdf", content=content)


def create_scripts_blueprint(
    upload_script_file: UploadScriptFile,
    list_scripts: ListScripts,
    get_script: GetScript,
    start_analysis: StartAnalysis,
    get_analysis: GetAnalysis,
    owned_files: OwnedFiles | None = None,
    durable_jobs: DurableJobs | None = None,
    drafts: DraftStore | None = None,
    manifests: AnalysisManifestReader | None = None,
    provider_config_json: str = "{}",
) -> Blueprint:
    bp = Blueprint("clearcut_scripts", __name__)

    @bp.route("/api/projects/<project_id>/script-files", methods=["POST"])
    def script_files_create(project_id: str) -> ResponseReturnValue:
        uploaded = _read_upload()
        if not isinstance(uploaded, _Upload):
            return uploaded

        def build() -> JsonDict:
            stored = upload_script_file.execute(project_id, uploaded.filename, uploaded.content)
            result = serializers.script_file_json(stored)
            if owned_files is not None:
                file_id = validators.new_id()
                owned_files.register_file(project_id, file_id, stored.gcs_uri)
                result["file_id"] = file_id
            return result

        return errors.run_use_case(build, status=201)

    @bp.route("/api/projects/<project_id>/scripts", methods=["GET"])
    def scripts_index(project_id: str) -> ResponseReturnValue:
        def build() -> list[JsonDict]:
            listings = list_scripts.execute(project_id)
            return [serializers.script_summary_json(listing) for listing in listings]

        return errors.run_use_case(build)

    @bp.route("/api/projects/<project_id>/scripts", methods=["POST"])
    def scripts_create(project_id: str) -> ResponseReturnValue:
        payload = validators.json_body()
        if durable_jobs is not None and drafts is None:
            return errors.error_response(503, "revision analysis is not configured")
        if durable_jobs is not None and drafts is not None:
            revision_id = payload.get("revision_id")
            if not isinstance(revision_id, str) or not revision_id or "/" in revision_id:
                return errors.error_response(400, "an immutable saved revision_id is required")
            jurisdiction = validators.resolve_jurisdiction(
                str(payload.get("jurisdiction_code", ""))
            )
            if not isinstance(jurisdiction, Jurisdiction):
                return jurisdiction
            command = NewAnalysis(
                validators.new_id(),
                validators.new_id(),
                project_id,
                g.organization_id,
                g.identity.user_id,
                revision_id,
                jurisdiction.code,
                provider_config_json,
                datetime.now(UTC),
            )

            def enqueue() -> JsonDict:
                revision = drafts.revision(project_id, revision_id)
                return _durable_json(durable_jobs.enqueue(command, revision))

            return errors.run_use_case(
                enqueue,
                status=202,
                location=f"/api/projects/{project_id}/analyses/{command.analysis_id}",
            )
        reference = "file_id" if owned_files is not None else "gcs_uri"
        gcs_uri = validators.require_field(payload, reference)
        if not isinstance(gcs_uri, str):
            return gcs_uri
        version = validators.require_version(payload)
        if not isinstance(version, int):
            return version
        jurisdiction = validators.resolve_jurisdiction(str(payload.get("jurisdiction_code", "")))
        if not isinstance(jurisdiction, Jurisdiction):
            return jurisdiction
        # Both ids are the server's. The script does not exist yet -- it is
        # what the queued run produces -- so the 202 names the analysis to
        # poll rather than the script to read.
        analysis_id = validators.new_id()
        script_id = validators.new_id()

        def build() -> JsonDict:
            uri = (
                owned_files.resolve_file(project_id, gcs_uri)
                if owned_files is not None
                else gcs_uri
            )
            job = start_analysis.execute(
                project_id, analysis_id, script_id, version, uri, jurisdiction
            )
            return serializers.analysis_job_json(job)

        return errors.run_use_case(
            build,
            status=202,
            location=f"/api/projects/{project_id}/analyses/{analysis_id}",
        )

    @bp.route("/api/projects/<project_id>/scripts/<script_id>", methods=["GET"])
    def scripts_show(project_id: str, script_id: str) -> ResponseReturnValue:
        def build() -> JsonDict:
            result = serializers.script_json(get_script.execute(project_id, script_id))
            if manifests is not None:
                manifest = manifests.manifest(project_id, script_id)
                for key in (
                    "revision_id",
                    "revision_draft_version",
                    "scene_anchors",
                    "clearance_bindings",
                    "coverage_gaps",
                ):
                    result[key] = manifest[key]
                result["settings_version"] = manifest.get("settings_version")
            return result

        return errors.run_use_case(build)

    @bp.route("/api/projects/<project_id>/analyses/<analysis_id>", methods=["GET"])
    def analyses_show(project_id: str, analysis_id: str) -> ResponseReturnValue:
        def build() -> JsonDict:
            if durable_jobs is not None:
                try:
                    if analysis_id == "current":
                        current = durable_jobs.current(project_id)
                        return _durable_json(current) if current else {"analysis": None}
                    return _durable_json(durable_jobs.get(project_id, analysis_id))
                except RecordNotFound:
                    pass
            return serializers.analysis_job_json(get_analysis.execute(project_id, analysis_id))

        return errors.run_use_case(build)

    @bp.route("/api/projects/<project_id>/analyses/<analysis_id>/cancellation", methods=["POST"])
    def analyses_cancel(project_id: str, analysis_id: str) -> ResponseReturnValue:
        if durable_jobs is None:
            return errors.error_response(409, "this demo analysis does not support cancellation")
        return errors.run_use_case(
            lambda: _durable_json(
                durable_jobs.request_cancel(
                    project_id, analysis_id, g.identity.user_id, datetime.now(UTC)
                )
            )
        )

    return bp


def _durable_json(job: DurableJob) -> JsonDict:
    return {
        "analysis_id": job.request.analysis_id,
        "project_id": job.request.project_id,
        "script_id": job.request.script_id,
        "revision_id": job.request.revision_id,
        "state": job.state,
        "stage": job.stage,
        "created_at": job.request.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "error": job.error_code,
        "version": job.request.script_version,
        "attempt": job.attempt,
        "cancel_requested": job.cancel_requested,
    }
