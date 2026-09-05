"""The six domains, merged into one OpenAPI document.

`DOMAINS` is the whole registry. A domain module declares its own `TAG`,
`PATHS` and `SCHEMAS` next to the handlers that serve them, and this module
is the only place that knows there are six of them -- which is what lets
Swagger render six collapsible groups instead of one undifferentiated list.
An API with no domains in its document has no domains (ADR 0012).

Both merges **raise** rather than letting one domain quietly win. A duplicate
schema name means one domain is about to serve a shape it does not describe;
a duplicate `(path, method)` means two blueprints answer the same request and
only registration order decides which. Neither failure shows up anywhere but
in a client, so both are turned into a startup failure here.

The document is built on every call rather than cached at import time, so a
test that builds an app twice sees two independent documents and nothing
depends on module import order.
"""

from collections.abc import Iterable
from typing import Any, Protocol

from clearcut.adapters.http import (
    bible,
    projects,
    questions,
    schemas,
    scripts,
    system,
    tracker,
)

JsonDict = dict[str, Any]

_METHODS = ("get", "post", "put", "patch", "delete")


class Domain(Protocol):
    """What `openapi.py` needs from a domain module.

    A `Protocol` rather than a base class or a registration decorator: the
    six modules are modules, and this states what they have in common
    without asking them to inherit anything or to run code at import time.
    """

    TAG: str
    TAG_DESCRIPTION: str
    PATHS: JsonDict
    SCHEMAS: JsonDict


DOMAINS: tuple[Domain, ...] = (system, projects, scripts, tracker, bible, questions)

INFO: JsonDict = {
    "title": "ClearCut API",
    "version": "1.0.0",
    "summary": "Agentic script clearance for independent film production.",
    "description": (
        "Upload a screenplay version and every rights event that could stop the film "
        "comes back with the law it triggers, who holds the rights, and an action to "
        "resolve it.\n\n"
        "Two rules hold everywhere:\n\n"
        "- Analysis is asynchronous. `POST /api/projects/{project_id}/scripts` answers "
        "202 with an analysis id and a `Location` header. Document AI and Gemini take "
        "minutes on a feature-length script, which outlives the Cloud Run request "
        "timeout. The browser polls "
        "`GET /api/projects/{project_id}/analyses/{analysis_id}` instead.\n"
        "- Every path is scoped to its project. There is no top-level "
        "`/api/tracker-items/...`: an item id alone leaves the server unable to answer "
        '"may this caller read it" without a second lookup.\n\n'
        "`GET /api/health` reports whether this instance serves real analysis or the "
        "fixed demo sample. Check it before trusting a finding."
    ),
}


def _duplicate_operation(path: str, method: str) -> ValueError:
    """A plain `ValueError`, not an error class of this package's own.

    Every exception type an adapter module defines has to subclass exactly
    one of the three types in `domain/errors.py`, so that `application/` can
    catch it by name without importing an adapter
    (`tests/unit/test_error_boundaries.py`). None of the three fits: this is
    not a record that is missing or a source that is down, it is two modules
    disagreeing about who serves a request, found while the document is
    built. It reaches no handler and no client -- it stops startup.
    """
    return ValueError(
        f"{method.upper()} {path} is declared by more than one domain; "
        "two blueprints answering one request leaves registration order deciding"
    )


def merge_paths(sources: Iterable[JsonDict]) -> JsonDict:
    """Every source's paths in one mapping, raising on a duplicate operation.

    Two domains may not share a path at all here, which is stricter than
    OpenAPI needs: a shared path would mean one resource split across two
    modules, and the partition exists precisely so that does not happen.
    """
    merged: JsonDict = {}
    for source in sources:
        for path, operations in source.items():
            existing = merged.setdefault(path, {})
            for method, operation in operations.items():
                if method in existing:
                    raise _duplicate_operation(path, method)
                existing[method] = operation
    return merged


def build_spec() -> JsonDict:
    """The served document: the six domains' paths, schemas and tags."""
    return {
        "openapi": "3.1.0",
        "info": INFO,
        "servers": [{"url": "/", "description": "The service serving this document."}],
        "tags": [{"name": domain.TAG, "description": domain.TAG_DESCRIPTION} for domain in DOMAINS],
        "paths": merge_paths(domain.PATHS for domain in DOMAINS),
        "components": {
            "schemas": schemas.merge_schemas(
                [schemas.SHARED, *(domain.SCHEMAS for domain in DOMAINS)]
            )
        },
    }


def operations(spec: JsonDict) -> set[tuple[str, str]]:
    """Every `(path, method)` the document declares, upper-cased.

    Shared with the drift test rather than reimplemented there: a document
    reader that disagreed with the document builder about what counts as an
    operation would make the drift test pass over a real drift. `parameters`
    is a path-level key, not a method, which is why the method names are
    listed rather than inferred from what is present.
    """
    return {
        (path, method.upper())
        for path, item in spec["paths"].items()
        for method in _METHODS
        if method in item
    }
