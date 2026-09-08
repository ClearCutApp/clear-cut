"""Private documents and screenplay import/export contract."""

from typing import Any

SCHEMAS: dict[str, Any] = {
    "ProjectDocument": {
        "type": "object",
        "required": [
            "file_id",
            "organization_id",
            "project_id",
            "filename",
            "content_type",
            "sha256",
            "kind",
            "created_by",
            "created_at",
            "revision_id",
            "size_bytes",
        ],
        "properties": {
            "file_id": {"type": "string"},
            "organization_id": {"type": "string"},
            "project_id": {"type": "string"},
            "filename": {"type": "string"},
            "content_type": {"type": "string"},
            "sha256": {"type": "string"},
            "kind": {"type": "string"},
            "created_by": {"type": "string"},
            "created_at": {"type": "string"},
            "revision_id": {"type": "string"},
            "size_bytes": {"type": "integer", "minimum": 1},
        },
    },
    "DocumentPage": {
        "type": "object",
        "required": ["documents", "next_before"],
        "properties": {
            "documents": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/ProjectDocument"},
            },
            "next_before": {"type": ["string", "null"]},
        },
    },
    "ScreenplayImportResult": {
        "type": "object",
        "required": ["draft", "original", "warnings"],
        "properties": {
            "draft": {"$ref": "#/components/schemas/ScreenplayDraft"},
            "original": {"$ref": "#/components/schemas/ProjectDocument"},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
    },
}
PATHS: dict[str, Any] = {
    "/api/projects/{project_id}/documents": {
        "get": {
            "tags": ["Documents"],
            "operationId": "listDocuments",
            "summary": "listDocuments",
            "parameters": [
                {
                    "name": "project_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                },
                {
                    "name": "before",
                    "in": "query",
                    "schema": {"type": "string"},
                    "description": "Exclusive last file ID cursor; at most 50 files.",
                },
            ],
            "responses": {
                "200": {
                    "description": "Owned immutable file or saved screenplay",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/DocumentPage"}
                        }
                    },
                },
                "400": {"description": "Invalid document or unsupported format"},
                "404": {"description": "Project, document or revision inaccessible"},
                "409": {"description": "Draft changed; original retained in project documents"},
                "413": {"description": "File exceeds 25 MiB"},
            },
        },
        "post": {
            "tags": ["Documents"],
            "operationId": "uploadDocument",
            "summary": "uploadDocument",
            "parameters": [
                {"name": "project_id", "in": "path", "required": True, "schema": {"type": "string"}}
            ],
            "responses": {
                "201": {
                    "description": "Owned immutable file or saved screenplay",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ProjectDocument"}
                        }
                    },
                },
                "400": {"description": "Invalid document or unsupported format"},
                "404": {"description": "Project, document or revision inaccessible"},
                "409": {"description": "Draft changed; original retained in project documents"},
                "413": {"description": "File exceeds 25 MiB"},
            },
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["file"],
                            "properties": {"file": {"type": "string", "format": "binary"}},
                        }
                    }
                },
            },
        },
    },
    "/api/projects/{project_id}/documents/{file_id}": {
        "get": {
            "tags": ["Documents"],
            "operationId": "downloadDocument",
            "summary": "downloadDocument",
            "parameters": [
                {
                    "name": "project_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                },
                {"name": "file_id", "in": "path", "required": True, "schema": {"type": "string"}},
            ],
            "responses": {
                "200": {
                    "description": "Owned immutable file or saved screenplay",
                    "content": {
                        "application/octet-stream": {
                            "schema": {"type": "string", "format": "binary"}
                        }
                    },
                },
                "400": {"description": "Invalid document or unsupported format"},
                "404": {"description": "Project, document or revision inaccessible"},
                "409": {"description": "Draft changed; original retained in project documents"},
                "413": {"description": "File exceeds 25 MiB"},
            },
        }
    },
    "/api/projects/{project_id}/imports": {
        "post": {
            "tags": ["Documents"],
            "operationId": "importScreenplay",
            "summary": "importScreenplay",
            "parameters": [
                {"name": "project_id", "in": "path", "required": True, "schema": {"type": "string"}}
            ],
            "responses": {
                "201": {
                    "description": "Owned immutable file or saved screenplay",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ScreenplayImportResult"}
                        }
                    },
                },
                "400": {"description": "Invalid document or unsupported format"},
                "404": {"description": "Project, document or revision inaccessible"},
                "409": {"description": "Draft changed; original retained in project documents"},
                "413": {"description": "File exceeds 25 MiB"},
            },
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["file", "expected_version"],
                            "properties": {
                                "file": {"type": "string", "format": "binary"},
                                "expected_version": {"type": "integer", "minimum": 0},
                            },
                        }
                    }
                },
            },
        }
    },
    "/api/projects/{project_id}/revisions/{revision_id}/exports/{format}": {
        "get": {
            "tags": ["Documents"],
            "operationId": "exportScreenplay",
            "summary": "exportScreenplay",
            "parameters": [
                {
                    "name": "project_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                },
                {
                    "name": "revision_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                },
                {
                    "name": "format",
                    "in": "path",
                    "required": True,
                    "schema": {"enum": ["pdf", "fdx"]},
                },
            ],
            "responses": {
                "200": {
                    "description": "Owned immutable file or saved screenplay",
                    "content": {
                        "application/octet-stream": {
                            "schema": {"type": "string", "format": "binary"}
                        }
                    },
                },
                "400": {"description": "Invalid document or unsupported format"},
                "404": {"description": "Project, document or revision inaccessible"},
                "409": {"description": "Draft changed; original retained in project documents"},
                "413": {"description": "File exceeds 25 MiB"},
            },
        }
    },
}
