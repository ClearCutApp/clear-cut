"""The OpenAPI fragments every domain module builds its `PATHS` out of.

Flask stays (ADR 0012), so this document is written rather than generated
from type hints. That is a weaker guarantee than a generator gives, and the
drift test in `tests/unit/adapters/test_openapi.py` is what makes it safe:
the served document and `docs/api/openapi.yaml` must describe the same
operations, checked in both directions.

The helpers below exist so a domain module declares an operation in about as
many lines as its handler takes, and so the repeated shapes -- a JSON body, an
array response, a path parameter, the error responses every operation carries
-- are written once. `SHARED` holds the four schemas more than one domain
names; a schema only one domain uses belongs in that domain's own `SCHEMAS`,
where it sits next to the handler that returns it.

`merge_schemas` **raises** on a duplicate name rather than letting one domain
silently overwrite another's. Two domains that both define `Finding` mean one
of them is about to serve a shape it does not describe, and the failure that
follows would surface in a client, not here.
"""

from collections.abc import Iterable, Mapping
from typing import Any

JsonDict = dict[str, Any]


def _duplicate_schema_name(name: str) -> ValueError:
    """A plain `ValueError`, for the reason `openapi.py` records: an error
    class defined in an adapter module must classify under one of the three
    domain error types, and a document that describes one shape twice is a
    startup failure rather than a failed request."""
    return ValueError(
        f"schema {name!r} is defined by more than one domain; "
        "move it to schemas.SHARED or rename one of them"
    )


def ref(name: str) -> JsonDict:
    """A reference to a schema in `components/schemas`."""
    return {"$ref": f"#/components/schemas/{name}"}


def json_of(schema: JsonDict) -> JsonDict:
    """An `application/json` content block carrying `schema`."""
    return {"application/json": {"schema": schema}}


def json_array_of(schema: JsonDict) -> JsonDict:
    """An `application/json` content block carrying an array of `schema`.

    Its own helper because an array response typed as an object is a mistake
    that reads correctly: the document says `type: object`, the handler
    returns a list, and nothing but a client notices.
    """
    return json_of({"type": "array", "items": schema})


def body(schema: JsonDict) -> JsonDict:
    """A required JSON request body."""
    return {"required": True, "content": json_of(schema)}


def ok(description: str, content: JsonDict) -> JsonDict:
    return {"description": description, "content": content}


def created(description: str, content: JsonDict, *, location: str) -> JsonDict:
    """A 201 or 202 that hands back the path the client follows next.

    `location` is the header's description, not its value: the value is the
    handler's, and a document that hardcoded one would be describing a single
    record rather than the operation.
    """
    return {
        "description": description,
        "headers": {
            "Location": {
                "description": location,
                "required": True,
                "schema": {"type": "string"},
            }
        },
        "content": content,
    }


def failure(description: str) -> JsonDict:
    """One error response: the shape is always `Error`, only the reason varies."""
    return {"description": description, "content": json_of(ref("Error"))}


def path_param(name: str, description: str) -> JsonDict:
    return {
        "name": name,
        "in": "path",
        "required": True,
        "description": description,
        "schema": {"type": "string", "minLength": 1},
    }


PROJECT_ID = path_param("project_id", "The project that owns the record.")
SCRIPT_ID = path_param("script_id", "One script version.")
ANALYSIS_ID = path_param(
    "analysis_id", "One queued analysis, as returned by the 202 that created it."
)
ITEM_ID = path_param("item_id", "One tracker item.")

BAD_REQUEST = failure("A required field is missing or invalid. Nothing was written.")
NOT_FOUND = failure("No record at this path.")
INTERNAL_ERROR = failure(
    "The server failed for a reason it does not attribute. "
    "The body carries a message and never a stack trace."
)

SHARED: JsonDict = {
    "Error": {
        "type": "object",
        "description": "The one error shape every failing response returns.",
        "required": ["error"],
        "properties": {
            "error": {
                "type": "string",
                "description": "What went wrong, in one sentence, safe to show a producer.",
            }
        },
        "additionalProperties": False,
    },
    "Citation": {
        "type": "object",
        "description": "One source backing a finding or an answer.",
        "required": ["uri", "title", "snippet"],
        "properties": {
            "uri": {"type": "string"},
            "title": {"type": "string"},
            "snippet": {"type": "string"},
        },
        "additionalProperties": False,
    },
    "FactKind": {
        "type": "string",
        "enum": ["LORE", "POLICY"],
        "description": (
            "`LORE` facts feed the continuity audit; `POLICY` facts feed the policy audit."
        ),
    },
    "BibleFact": {
        "type": "object",
        "required": ["fact_id", "kind", "text", "source"],
        "properties": {
            "fact_id": {
                "type": "string",
                "description": "Assigned by the server as the next `FACT-NNN` in this project.",
            },
            "kind": ref("FactKind"),
            "text": {"type": "string"},
            "source": {
                "type": "string",
                "description": (
                    "Where the fact comes from, so a finding that cites it can be checked."
                ),
            },
        },
        "additionalProperties": False,
    },
}


def merge_schemas(sources: Iterable[Mapping[str, JsonDict]]) -> JsonDict:
    """Every source's schemas in one mapping, raising on a duplicate name."""
    merged: JsonDict = {}
    for source in sources:
        for name, schema in source.items():
            if name in merged:
                raise _duplicate_schema_name(name)
            merged[name] = schema
    return merged
