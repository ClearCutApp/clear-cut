"""System: liveness, and the machine-readable description of this API.

`GET /api/health` is what lets a browser tell planted data from real data.
`CLEARCUT_MODE=mock` serves the scenario in `adapters/demo/scenario.py`, and
until this existed the SPA rendered constants with exactly the confidence it
renders a Gemini extraction. The mode arrives as an argument because no
adapter module reads the environment (AGENT.md section 2 rule 4).

The document arrives as an argument too, for a narrower reason: `openapi.py`
imports every domain module to build it, and this is one of them. Taking a
callable keeps the dependency pointing one way -- `openapi` knows `system`,
never the reverse -- and lets a test serve a document it wrote itself.
"""

from collections.abc import Callable
from typing import Any

from flask import Blueprint, jsonify
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import schemas

JsonDict = dict[str, Any]

TAG = "System"

TAG_DESCRIPTION = "Liveness and the machine-readable description of this API."

SWAGGER_UI = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>ClearCut API</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  </head>
  <body>
    <div id="swagger"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.onload = () => {
        window.ui = SwaggerUIBundle({
          url: "/api/openapi.json",
          dom_id: "#swagger",
          deepLinking: true,
        });
      };
    </script>
  </body>
</html>
"""

SCHEMAS: JsonDict = {
    "Health": {
        "type": "object",
        "required": ["mode"],
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["mock", "live"],
                "description": (
                    "`mock` serves the planted demo scenario; `live` runs real analysis."
                ),
            }
        },
        "additionalProperties": False,
    }
}

PATHS: JsonDict = {
    "/api/health": {
        "get": {
            "tags": [TAG],
            "operationId": "getHealth",
            "summary": "Whether this instance runs live or serves the demo sample",
            "description": (
                "`mock` means every scene, finding and tracker item came from the "
                "planted scenario rather than from a real analysis."
            ),
            "responses": {
                "200": schemas.ok(
                    "The mode this instance runs under.",
                    schemas.json_of(schemas.ref("Health")),
                ),
                "500": schemas.INTERNAL_ERROR,
            },
        }
    },
    "/api/openapi.json": {
        "get": {
            "tags": [TAG],
            "operationId": "getOpenApiDocument",
            "summary": "This document, as JSON, from the running service",
            "responses": {
                "200": schemas.ok(
                    "An OpenAPI document describing the routes this instance serves.",
                    schemas.json_of({"type": "object", "additionalProperties": True}),
                ),
                "500": schemas.INTERNAL_ERROR,
            },
        }
    },
    "/api/docs": {
        "get": {
            "tags": [TAG],
            "operationId": "getApiDocs",
            "summary": "Swagger UI over the document above",
            "responses": {
                "200": {
                    "description": "An HTML page.",
                    "content": {"text/html": {"schema": {"type": "string"}}},
                },
                "500": schemas.INTERNAL_ERROR,
            },
        }
    },
}


def create_system_blueprint(mode: str, spec: Callable[[], JsonDict]) -> Blueprint:
    """Health, the OpenAPI document, and a Swagger UI over it.

    Register before the SPA blueprint, whose catch-all answers every
    unmatched path: registered after it, all three become its JSON 404.
    """
    bp = Blueprint("clearcut_system", __name__)

    @bp.route("/api/health")
    def health() -> ResponseReturnValue:
        return jsonify({"mode": mode})

    @bp.route("/api/openapi.json")
    def openapi_document() -> ResponseReturnValue:
        return jsonify(spec())

    @bp.route("/api/docs")
    def docs() -> ResponseReturnValue:
        return SWAGGER_UI, 200, {"Content-Type": "text/html; charset=utf-8"}

    return bp
