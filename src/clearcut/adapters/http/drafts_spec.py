"""Draft/revision wire contract with stable screenplay block identifiers."""

from typing import Any

Json = dict[str, Any]
SCHEMAS: Json = {
    "ScreenplayDocument": {
        "type": "object",
        "required": ["type", "content"],
        "properties": {
            "type": {"const": "doc"},
            "content": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20000,
                "items": {
                    "type": "object",
                    "required": ["type", "attrs"],
                    "properties": {
                        "type": {"const": "paragraph"},
                        "attrs": {
                            "type": "object",
                            "required": ["blockId", "sceneId", "kind"],
                            "properties": {
                                "blockId": {"type": "string", "minLength": 1, "maxLength": 128},
                                "sceneId": {"type": "string", "minLength": 1, "maxLength": 128},
                                "kind": {
                                    "enum": [
                                        "scene-heading",
                                        "action",
                                        "character",
                                        "dialogue",
                                        "parenthetical",
                                        "transition",
                                    ]
                                },
                            },
                        },
                        "content": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["type"],
                                "properties": {
                                    "type": {"enum": ["text", "hardBreak"]},
                                    "text": {"type": "string"},
                                    "marks": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {"type": {"enum": ["bold", "italic"]}},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "ScreenplayDraft": {
        "type": "object",
        "required": ["project_id", "version", "document", "updated_at", "updated_by"],
        "properties": {
            "project_id": {"type": "string"},
            "version": {"type": "integer", "minimum": 0},
            "document": {
                "anyOf": [{"$ref": "#/components/schemas/ScreenplayDocument"}, {"type": "null"}]
            },
            "updated_at": {"type": "string"},
            "updated_by": {"type": "string"},
        },
    },
    "ScreenplayRevision": {
        "type": "object",
        "required": [
            "revision_id",
            "project_id",
            "draft_version",
            "sha256",
            "created_at",
            "created_by",
        ],
        "properties": {
            "revision_id": {"type": "string"},
            "project_id": {"type": "string"},
            "draft_version": {"type": "integer"},
            "sha256": {"type": "string"},
            "created_at": {"type": "string"},
            "created_by": {"type": "string"},
            "document": {"$ref": "#/components/schemas/ScreenplayDocument"},
        },
    },
    "RevisionPage": {
        "type": "object",
        "required": ["revisions", "next_before_version"],
        "properties": {
            "revisions": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/ScreenplayRevision"},
            },
            "next_before_version": {"type": ["integer", "null"]},
        },
    },
}
PATHS: Json = {}
for suffix, operations in {
    "draft": {"get": ("getDraft", "ScreenplayDraft"), "put": ("saveDraft", "ScreenplayDraft")},
    "revisions": {
        "get": ("listRevisions", "RevisionPage"),
        "post": ("freezeRevision", "ScreenplayRevision"),
    },
    "revisions/{revision_id}": {"get": ("getRevision", "ScreenplayRevision")},
}.items():
    path = "/api/projects/{project_id}/" + suffix
    PATHS[path] = {}
    for method, (operation_id, schema) in operations.items():
        operation: Json = {
            "tags": ["Screenplay editor"],
            "operationId": operation_id,
            "summary": operation_id,
            "parameters": [
                {"name": "project_id", "in": "path", "required": True, "schema": {"type": "string"}}
            ],
            "responses": {
                "201" if method == "post" else "200": {
                    "description": "Saved document or immutable revision",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/" + schema}}
                    },
                },
                "400": {"description": "Invalid document or expected version"},
                "401": {"description": "Verified identity required"},
                "404": {"description": "Project or revision inaccessible"},
                "409": {
                    "description": (
                        "Draft changed; response includes current_version. "
                        "Preserve local edits before reloading."
                    )
                },
            },
        }
        if "{revision_id}" in suffix:
            operation["parameters"].append(
                {
                    "name": "revision_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
            )
        if suffix == "revisions" and method == "get":
            operation["parameters"].append(
                {
                    "name": "before_version",
                    "in": "query",
                    "schema": {"type": "integer", "minimum": 1},
                    "description": "Exclusive cursor; at most 50 revisions per page.",
                }
            )
        if method in {"put", "post"}:
            fields: Json = {"expected_version": {"type": "integer", "minimum": 0}}
            if method == "put":
                fields["document"] = {"$ref": "#/components/schemas/ScreenplayDocument"}
            operation["requestBody"] = {
                "required": True,
                "description": (
                    "Canonical screenplay JSON is limited to 8 MiB; "
                    "block IDs unique and scene IDs stable."
                ),
                "content": {
                    "application/json": {
                        "schema": {"type": "object", "required": list(fields), "properties": fields}
                    }
                },
            }
        PATHS[path][method] = operation
