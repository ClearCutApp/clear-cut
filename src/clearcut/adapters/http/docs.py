"""An OpenAPI document and a Swagger UI over it.

The deployed service offered no way to see what it does: reading `routes.py`
was the only way to learn a request shape. This makes the API explorable from
the same URL that serves it.

The spec describes the routes that exist, not the ones SDD section 4.2
specifies. Three of those are unbuilt by ADR 0011's ruling, and documenting
them would send a reader hunting for a fault in their own request. A test
compares this document against Flask's own URL map in both directions, so the
two cannot drift.

Its own blueprint for the same reason as `health.py`: it maps to no use case,
and `create_blueprint` takes use cases.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify
from flask.typing import ResponseReturnValue

_SWAGGER_UI = """<!doctype html>
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

_JSON = {"application/json": {"schema": {"type": "object"}}}


def _spec() -> dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "ClearCut API",
            "version": "0.1.0",
            "description": (
                "Agentic script clearance. Upload a screenplay version and every "
                "rights event that could stop the film comes back with the law it "
                "triggers, who holds the rights, and an action to resolve it.\n\n"
                "`GET /api/health` reports whether this instance is serving real "
                "analysis or the fixed demo sample. Check it before trusting a "
                "finding."
            ),
        },
        "paths": {
            "/api/docs": {
                "get": {
                    "summary": "This page",
                    "responses": {"200": {"description": "Swagger UI over the document below"}},
                }
            },
            "/api/openapi.json": {
                "get": {
                    "summary": "This document",
                    "responses": {"200": {"description": "the OpenAPI 3 spec", "content": _JSON}},
                }
            },
            "/api/health": {
                "get": {
                    "summary": "Whether this instance runs live or serves the demo sample",
                    "responses": {"200": {"description": "mock or live", "content": _JSON}},
                }
            },
            "/api/projects/{project_id}/scripts": {
                "post": {
                    "summary": "Create a script version, which returns its analysis",
                    "parameters": [
                        {
                            "name": "project_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "description": (
                        "`version` of 1 runs the full pipeline; greater than 1 runs the "
                        "delta path, re-analyzing only scenes whose content hash changed."
                    ),
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["gcs_uri", "version", "jurisdiction_code"],
                                    "properties": {
                                        "gcs_uri": {"type": "string"},
                                        "version": {"type": "integer", "minimum": 1},
                                        "jurisdiction_code": {"type": "string", "example": "AR"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "scenes, findings, tracker items", "content": _JSON},
                        "400": {"description": "a field is missing or invalid"},
                        "404": {"description": "version > 1 with no stored previous version"},
                        "502": {"description": "an upstream service failed"},
                    },
                }
            },
            "/api/projects/{project_id}/tracker-items": {
                "get": {
                    "summary": "Tracker items for a project",
                    "parameters": [
                        {
                            "name": "project_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "items, newest version per id", "content": _JSON},
                        "404": {"description": "no such project in the path"},
                    },
                }
            },
            "/api/tracker-items/{item_id}": {
                "patch": {
                    "summary": "Move one item between states",
                    "parameters": [
                        {
                            "name": "item_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["state"],
                                    "properties": {
                                        "state": {
                                            "type": "string",
                                            "enum": ["BLOCKED", "IN_PROGRESS", "CLEARED"],
                                        }
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "the item at its new version", "content": _JSON},
                        "400": {"description": "unrecognized state"},
                        "404": {"description": "no such item"},
                    },
                }
            },
            "/api/tracker-items/{item_id}/actions": {
                "post": {
                    "summary": "Draft an outreach email, or notify a stakeholder",
                    "description": (
                        "`draft_email` fills the outreach template and stores it on the "
                        "item; the system never sends it. `notify` posts to the "
                        "configured webhook."
                    ),
                    "parameters": [
                        {
                            "name": "item_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["action"],
                                    "properties": {
                                        "action": {
                                            "type": "string",
                                            "enum": ["draft_email", "notify"],
                                        },
                                        "reason": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "the updated item", "content": _JSON},
                        "404": {"description": "no such item"},
                        "502": {"description": "the webhook rejected the notification"},
                    },
                }
            },
            "/api/projects/{project_id}/questions": {
                "post": {
                    "summary": "Ask about the project's clearance state",
                    "parameters": [
                        {
                            "name": "project_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["jurisdiction_code"],
                                    "properties": {
                                        "jurisdiction_code": {"type": "string", "example": "AR"},
                                        "question": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "answer, bible facts, citations", "content": _JSON},
                        "400": {"description": "a field is missing or invalid"},
                        "502": {"description": "an upstream service failed"},
                    },
                }
            },
        },
    }


def create_docs_blueprint() -> Blueprint:
    """Serves the OpenAPI document and a Swagger UI over it.

    Register before the SPA blueprint, whose catch-all would otherwise turn
    both into its JSON 404 for `/api` paths.
    """
    bp = Blueprint("clearcut_docs", __name__)

    @bp.route("/api/openapi.json")
    def openapi() -> ResponseReturnValue:
        return jsonify(_spec())

    @bp.route("/api/docs")
    def docs() -> ResponseReturnValue:
        return _SWAGGER_UI, 200, {"Content-Type": "text/html; charset=utf-8"}

    return bp
