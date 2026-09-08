"""The one place a raised error becomes a status code.

Every route in this package answers through `run_use_case`, so the mapping
from domain error to status exists once rather than once per handler. A
handler that grew its own `except` block would be a second opinion about what
a `RecordNotFound` means, and the two would drift the first time one of them
gained a case.

`build` both calls the use case and serializes its result, so an error caught
here can never be a serialization bug wearing a 404's clothes.

Every unmapped exception becomes a JSON 500 with no stack trace. That is this
package's own edge-of-the-system catch, not a violation of the bare-except
guard in `tests/unit/test_error_boundaries.py`, which scopes to
`application/`.
"""

from collections.abc import Callable
from typing import Any

from flask import Response, jsonify
from flask.typing import ResponseReturnValue

from clearcut.domain.document import InvalidDocument
from clearcut.domain.durable_analysis import AnalysisBusy
from clearcut.domain.errors import RecordNotFound, SourceUnavailable
from clearcut.domain.identity import AccessDenied
from clearcut.domain.screenplay import DraftConflict, InvalidScreenplay
from clearcut.domain.tracker import InvalidClearance, TrackerConflict
from clearcut.domain.voice import InvalidRecording
from clearcut.domain.workspace import InvalidWorkspace, WorkspaceConflict

JsonDict = dict[str, Any]
JsonBody = JsonDict | list[JsonDict] | Response

_INTERNAL_ERROR_MESSAGE = "internal error"


def error_response(status: int, message: str) -> ResponseReturnValue:
    """The one error shape every failing response returns: `{"error": ...}`."""
    return jsonify({"error": message}), status


def run_use_case(
    build: Callable[[], JsonBody],
    *,
    status: int = 200,
    location: str | None = None,
) -> ResponseReturnValue:
    """Calls `build` and maps whatever it raises to a status code.

    `status` and `location` carry the two things a successful write answers
    with that a read does not: 201 or 202, and the path the client polls or
    follows. They are arguments rather than a second function because the
    failure mapping is identical either way, and a 201 helper that forgot one
    of these cases is how a create route starts returning 200.
    """
    try:
        body = build()
    except WorkspaceConflict:
        return error_response(409, "workspace changed; reload before retrying")
    except AnalysisBusy:
        return error_response(409, "a project analysis is already active")
    except TrackerConflict as error:
        return jsonify({"error": str(error), "current_version": error.current_version}), 409
    except DraftConflict as error:
        return jsonify(
            {
                "error": "draft changed; recover your local copy before reloading",
                "current_version": error.current_version,
            }
        ), 409
    except (
        InvalidScreenplay,
        InvalidRecording,
        InvalidDocument,
        InvalidClearance,
        InvalidWorkspace,
    ) as error:
        return error_response(400, str(error))
    except AccessDenied:
        return error_response(403, "workspace does not allow this action")
    except RecordNotFound as error:
        return error_response(404, str(error))
    except SourceUnavailable:
        return error_response(502, "upstream service unavailable; try again")
    except Exception as error:
        if getattr(error, "code", None) == 413:
            return error_response(413, "request body too large")
        # Neither of the two mapped domain errors, and not `EnrichmentMissing`
        # either -- that one is caught inside the use case and never reaches
        # here (D23). A 500 with no stack trace is the honest answer: the
        # body carries a message and never internals.
        return error_response(500, _INTERNAL_ERROR_MESSAGE)
    if isinstance(body, Response):
        return body, status
    if location is None:
        return jsonify(body), status
    return jsonify(body), status, {"Location": location}
