"""The OpenAPI half of the Scripts domain.

Split out of `scripts.py` because that module would otherwise carry five
handlers, multipart parsing and twelve schemas in one file, well past
AGENT.md section 4's size guide. The split is by kind, not by subject: every
operation Scripts serves is described here and handled there, so a reader
looking for either finds all of it in one place.
"""

from typing import Any

from clearcut.adapters.http import schemas

JsonDict = dict[str, Any]

TAG = "Scripts"

TAG_DESCRIPTION = "Script uploads, script versions, and the analyses they queue."

_MAX_UPLOAD_DESCRIPTION = "A PDF, at most 25 MiB."

SCHEMAS: JsonDict = {
    "RiskLevel": {
        "type": "string",
        "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        "description": "How urgently a finding needs clearance action.",
    },
    "Category": {
        "type": "string",
        "enum": [
            "INDUSTRIAL_PROPERTY",
            "COPYRIGHT_WORKS",
            "PERSONALITY_IMAGE",
            "INTEGRATED_VISUAL",
            "LOCATIONS_PERMITS",
            "SPECIAL_SYMBOLS",
            "CONTINUITY",
            "POLICY",
        ],
        "description": "The eight IP categories a finding falls under.",
    },
    "NerLabel": {
        "type": "string",
        "enum": [
            "BRAND",
            "MUSIC_EXISTING",
            "MUSIC_ORIGINAL",
            "ART_LIT",
            "MEDIA_AV",
            "TALENT_CHARACTER",
            "REAL_PERSON",
            "PROPS_DESIGN",
            "LOCATION_PRIV",
            "LOCATION_PUB",
            "SPECIAL_SYMBOL",
        ],
        "description": "The eleven tags the extractor emits.",
    },
    "Span": {
        "type": "object",
        "description": (
            "One finding's position in one scene's text, computed server-side on read "
            "(ADR 0015). The browser highlights these offsets and never searches the "
            "text itself.\n\nA phrase that appears three times in a scene produces three "
            "spans, one per occurrence. Where two findings claim the same characters, "
            "the higher-risk one wins the range and the other has no span here; it is "
            "still listed among the scene's findings."
        ),
        "required": ["scene_number", "start", "end", "finding_id", "risk"],
        "properties": {
            "scene_number": {
                "type": "integer",
                "minimum": 1,
                "description": (
                    "The scene this span belongs to, repeated so a span survives being moved."
                ),
            },
            "start": {
                "type": "integer",
                "minimum": 0,
                "description": "Offset of the first character, counted in Unicode code points.",
            },
            "end": {
                "type": "integer",
                "minimum": 0,
                "description": "Offset one past the last character. Always greater than `start`.",
            },
            "finding_id": {"type": "string", "description": "The finding this span belongs to."},
            "risk": schemas.ref("RiskLevel"),
        },
        "additionalProperties": False,
    },
    "Scene": {
        "type": "object",
        "required": [
            "number",
            "heading",
            "page_start",
            "page_end",
            "text",
            "content_hash",
            "spans",
        ],
        "properties": {
            "number": {"type": "integer", "minimum": 1},
            "heading": {"type": "string"},
            "page_start": {"type": "integer", "minimum": 1},
            "page_end": {"type": "integer", "minimum": 1},
            "text": {
                "type": "string",
                "description": "The scene as written. `spans` offsets index into this string.",
            },
            "content_hash": {
                "type": "string",
                "description": (
                    "SHA-256 of the normalized text. Two versions share a hash when the "
                    "scene did not change, which is what the delta path joins on."
                ),
            },
            "spans": {
                "type": "array",
                "description": (
                    "Where in `text` this scene's findings were raised, ordered by `start` "
                    "and never overlapping. Empty when the scene raised none, and shorter "
                    "than the scene's finding count when a finding's `raw_text` does not "
                    "appear verbatim."
                ),
                "items": schemas.ref("Span"),
            },
        },
        "additionalProperties": False,
    },
    "Finding": {
        "type": "object",
        "description": "One detected clearance event.",
        "required": [
            "finding_id",
            "scene_number",
            "page",
            "raw_text",
            "category",
            "ner_label",
            "risk_level",
            "required_document",
            "citations",
            "contradicts",
        ],
        "properties": {
            "finding_id": {"type": "string"},
            "scene_number": {"type": "integer", "minimum": 1},
            "page": {"type": "integer", "minimum": 1},
            "raw_text": {
                "type": "string",
                "description": "The script fragment the finding was raised against.",
            },
            "category": schemas.ref("Category"),
            "ner_label": {
                "description": (
                    "Null for `CONTINUITY` and `POLICY` findings: those come from the "
                    "bible audit, so nothing in the script text was extracted for them."
                ),
                "oneOf": [schemas.ref("NerLabel"), {"type": "null"}],
            },
            "risk_level": schemas.ref("RiskLevel"),
            "required_document": {
                "type": "string",
                "description": "What must be obtained to clear this finding.",
            },
            "citations": {"type": "array", "items": schemas.ref("Citation")},
            "contradicts": {
                "description": (
                    "The `fact_id` of the bible fact this finding contradicts, on a "
                    "continuity finding. Null on every other kind."
                ),
                "type": ["string", "null"],
            },
        },
        "additionalProperties": False,
    },
    "ScriptFile": {
        "type": "object",
        "description": "One uploaded screenplay in Cloud Storage.",
        "required": ["gcs_uri", "filename", "size_bytes", "content_type"],
        "properties": {
            "gcs_uri": {
                "type": "string",
                "description": "Pass this to `POST /api/projects/{project_id}/scripts`.",
            },
            "filename": {"type": "string"},
            "size_bytes": {"type": "integer", "minimum": 1},
            "content_type": {"type": "string", "enum": ["application/pdf"]},
        },
        "additionalProperties": False,
    },
    "ScriptCreate": {
        "type": "object",
        "required": ["gcs_uri", "version", "jurisdiction_code"],
        "properties": {
            "gcs_uri": {
                "type": "string",
                "description": ("The URI `POST /api/projects/{project_id}/script-files` returned."),
            },
            "version": {
                "type": "integer",
                "minimum": 1,
                "description": (
                    "1 runs the full pipeline. Above 1 diffs against the stored previous "
                    "version and re-analyzes only the scenes whose content hash changed."
                ),
            },
            "jurisdiction_code": {"type": "string"},
        },
        "additionalProperties": False,
    },
    "AnalysisState": {
        "type": "string",
        "enum": ["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"],
        "description": (
            "`SUCCEEDED` and `FAILED` are terminal: a job in either never moves again, "
            "and a later run of the same script is a new analysis."
        ),
    },
    "AnalysisJob": {
        "type": "object",
        "required": [
            "analysis_id",
            "project_id",
            "script_id",
            "state",
            "created_at",
            "updated_at",
            "error",
            "version",
        ],
        "properties": {
            "analysis_id": {"type": "string"},
            "project_id": {"type": "string"},
            "script_id": {
                "type": "string",
                "description": (
                    "The script version this analysis produces. Assigned when the job is "
                    "queued, readable at `/api/projects/{project_id}/scripts/{script_id}` "
                    "once `state` is `SUCCEEDED`."
                ),
            },
            "state": schemas.ref("AnalysisState"),
            "created_at": {"type": "string", "format": "date-time"},
            "updated_at": {
                "type": "string",
                "format": "date-time",
                "description": (
                    "When this version was written. Polling compares it to spot a stalled run."
                ),
            },
            "error": {
                "type": "string",
                "description": (
                    "Why the run failed. Empty in every state but `FAILED`, and never "
                    "empty in `FAILED`."
                ),
            },
            "version": {
                "type": "integer",
                "minimum": 1,
                "description": (
                    "Each transition writes a new version rather than mutating this row."
                ),
            },
        },
        "additionalProperties": False,
    },
    "ScriptSummary": {
        "type": "object",
        "description": "One script version without its scenes or findings.",
        "required": [
            "script_id",
            "project_id",
            "version",
            "gcs_uri",
            "jurisdiction_code",
            "scene_count",
            "finding_count",
        ],
        "properties": {
            "script_id": {"type": "string"},
            "project_id": {"type": "string"},
            "version": {"type": "integer", "minimum": 1},
            "gcs_uri": {"type": "string"},
            "jurisdiction_code": {"type": "string"},
            "scene_count": {"type": "integer", "minimum": 0},
            "finding_count": {"type": "integer", "minimum": 0},
        },
        "additionalProperties": False,
    },
    "Script": {
        "type": "object",
        "description": (
            "One script version, with every scene and every finding raised against it."
        ),
        "required": [
            "script_id",
            "project_id",
            "version",
            "gcs_uri",
            "jurisdiction_code",
            "scenes",
            "findings",
        ],
        "properties": {
            "script_id": {"type": "string"},
            "project_id": {"type": "string"},
            "version": {"type": "integer", "minimum": 1},
            "gcs_uri": {"type": "string"},
            "jurisdiction_code": {"type": "string"},
            "scenes": {
                "type": "array",
                "description": "Ordered by `number`, which strictly increases.",
                "items": schemas.ref("Scene"),
            },
            "findings": {"type": "array", "items": schemas.ref("Finding")},
        },
        "additionalProperties": False,
    },
}

PATHS: JsonDict = {
    "/api/projects/{project_id}/script-files": {
        "parameters": [schemas.PROJECT_ID],
        "post": {
            "tags": [TAG],
            "operationId": "uploadScriptFile",
            "summary": "Upload a screenplay PDF and get back the URI to analyze",
            "description": (
                "Writes the PDF to Cloud Storage and returns its `gs://` URI. Nothing is "
                "parsed here: pass the returned `gcs_uri` to "
                "`POST /api/projects/{project_id}/scripts` to queue an analysis. The two "
                "steps are separate so a re-analysis of the same upload costs no second "
                "transfer."
            ),
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["file"],
                            "properties": {
                                "file": {
                                    "type": "string",
                                    "format": "binary",
                                    "description": _MAX_UPLOAD_DESCRIPTION,
                                }
                            },
                        },
                        "encoding": {"file": {"contentType": "application/pdf"}},
                    }
                },
            },
            "responses": {
                "201": schemas.ok("The stored object.", schemas.json_of(schemas.ref("ScriptFile"))),
                "400": schemas.failure(
                    "No file part, or a file that is not a PDF. ClearCut reads screenplays "
                    "through Document AI, which is configured for PDF alone."
                ),
                "413": schemas.failure("The file is over 25 MiB."),
                "502": schemas.failure("Cloud Storage rejected the write. Nothing was stored."),
                "500": schemas.INTERNAL_ERROR,
            },
        },
    },
    "/api/projects/{project_id}/scripts": {
        "parameters": [schemas.PROJECT_ID],
        "get": {
            "tags": [TAG],
            "operationId": "listScripts",
            "summary": "Every version of this project's script",
            "responses": {
                "200": schemas.ok(
                    "One entry per version, newest first. Scenes and findings are absent "
                    "here; read one version to get them.",
                    schemas.json_array_of(schemas.ref("ScriptSummary")),
                ),
                "404": schemas.NOT_FOUND,
                "500": schemas.INTERNAL_ERROR,
            },
        },
        "post": {
            "tags": [TAG],
            "operationId": "createScript",
            "summary": "Queue an analysis of one script version",
            "description": (
                "Answers 202 and returns immediately. `version` of 1 runs the full "
                "pipeline; greater than 1 runs the delta path, re-analyzing only the "
                "scenes whose content hash changed against the stored previous version."
                "\n\nPoll the `Location` path until `state` leaves `QUEUED` and `RUNNING`."
            ),
            "requestBody": schemas.body(schemas.ref("ScriptCreate")),
            "responses": {
                "202": schemas.created(
                    "The analysis was queued. The script itself does not exist yet, so "
                    "`Location` points at the analysis rather than at the script.",
                    schemas.json_of(schemas.ref("AnalysisJob")),
                    location="The path to poll for this analysis.",
                ),
                "400": schemas.BAD_REQUEST,
                "404": schemas.failure(
                    "No such project, or `version` above 1 with no stored previous version."
                ),
                "500": schemas.INTERNAL_ERROR,
            },
        },
    },
    "/api/projects/{project_id}/scripts/{script_id}": {
        "parameters": [schemas.PROJECT_ID, schemas.SCRIPT_ID],
        "get": {
            "tags": [TAG],
            "operationId": "getScript",
            "summary": "One script version, with its scenes, spans and findings",
            "description": (
                "Each scene carries a `spans` array: the character offsets in that "
                "scene's `text` that a finding was raised against. The server computes "
                "them while it reads the script, so a highlight is an offset the browser "
                "renders rather than a substring it searches for -- the same phrase can "
                "appear twice in a scene and only one occurrence be the finding."
            ),
            "responses": {
                "200": schemas.ok("The script version.", schemas.json_of(schemas.ref("Script"))),
                "404": schemas.NOT_FOUND,
                "500": schemas.INTERNAL_ERROR,
            },
        },
    },
    "/api/projects/{project_id}/analyses/{analysis_id}": {
        "parameters": [schemas.PROJECT_ID, schemas.ANALYSIS_ID],
        "get": {
            "tags": [TAG],
            "operationId": "getAnalysis",
            "summary": "The state of one queued analysis",
            "description": (
                "`SUCCEEDED` carries the `script_id` to read. `FAILED` carries a "
                "non-empty `error`. A run whose instance was reclaimed mid-run is "
                "reported as `FAILED` by the read that finds it stale, so a job never "
                "sits in `RUNNING` forever."
            ),
            "responses": {
                "200": schemas.ok(
                    "The analysis job at its newest version.",
                    schemas.json_of(schemas.ref("AnalysisJob")),
                ),
                "404": schemas.NOT_FOUND,
                "500": schemas.INTERNAL_ERROR,
            },
        },
    },
}
