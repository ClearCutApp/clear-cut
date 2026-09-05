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
from typing import Any

from flask import Blueprint, request
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import errors, scripts_spec, serializers, validators
from clearcut.application.get_analysis import GetAnalysis
from clearcut.application.get_script import GetScript
from clearcut.application.list_scripts import ListScripts
from clearcut.application.start_analysis import StartAnalysis
from clearcut.application.upload_script_file import UploadScriptFile
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
) -> Blueprint:
    bp = Blueprint("clearcut_scripts", __name__)

    @bp.route("/api/projects/<project_id>/script-files", methods=["POST"])
    def script_files_create(project_id: str) -> ResponseReturnValue:
        uploaded = _read_upload()
        if not isinstance(uploaded, _Upload):
            return uploaded

        def build() -> JsonDict:
            stored = upload_script_file.execute(project_id, uploaded.filename, uploaded.content)
            return serializers.script_file_json(stored)

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
        gcs_uri = validators.require_field(payload, "gcs_uri")
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
            job = start_analysis.execute(
                project_id, analysis_id, script_id, version, gcs_uri, jurisdiction
            )
            return serializers.analysis_job_json(job)

        return errors.run_use_case(
            build,
            status=202,
            location=f"/api/projects/{project_id}/analyses/{analysis_id}",
        )

    @bp.route("/api/projects/<project_id>/scripts/<script_id>", methods=["GET"])
    def scripts_show(project_id: str, script_id: str) -> ResponseReturnValue:
        return errors.run_use_case(
            lambda: serializers.script_json(get_script.execute(project_id, script_id))
        )

    @bp.route("/api/projects/<project_id>/analyses/<analysis_id>", methods=["GET"])
    def analyses_show(project_id: str, analysis_id: str) -> ResponseReturnValue:
        return errors.run_use_case(
            lambda: serializers.analysis_job_json(get_analysis.execute(project_id, analysis_id))
        )

    return bp
