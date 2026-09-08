"""Request-shape checks, each answering with the value or with a 400.

Every function here returns either the value the handler asked for or a
`ResponseReturnValue` the handler returns immediately, and the handler tells
the two apart with `isinstance`. A raised exception would be tidier to read
and would land in `run_use_case`'s generic catch as a 500, which is the wrong
answer for a request the client can fix.

Validation lives here rather than in a use case because "did this request
carry a version" is a fact about HTTP, not about clearance. What a version
*means* is the domain's, and `Jurisdiction` proves it: this module only turns
an unknown code into a 400, the lookup itself is `domain.jurisdiction`'s.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from flask import request
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import errors
from clearcut.domain.bible import FactKind
from clearcut.domain.errors import UnknownJurisdiction
from clearcut.domain.jurisdiction import Jurisdiction, jurisdiction_for
from clearcut.domain.tracker import TrackerState

JsonDict = dict[str, Any]

_ACCEPTED_STATES = tuple(state.value for state in TrackerState)
_ACCEPTED_FACT_KINDS = tuple(kind.value for kind in FactKind)


def json_body() -> JsonDict:
    """The request's JSON object, or an empty one.

    A malformed body reads as an absent one on purpose: the field checks
    below then name the field that is missing, which tells a caller more than
    "invalid JSON" does about a request that carried none.
    """
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def now() -> str:
    """The current time in the format `TrackerItem.updated_at` carries.

    Read from the clock, never from the request: an `updated_at` echoing a
    client-supplied value is an audit record the client wrote.
    """
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id() -> str:
    """A fresh opaque id for a resource the server names.

    Server-assigned rather than client-supplied, so two producers cannot
    collide by typing the same word, and a client cannot address a record it
    was never given.
    """
    return uuid.uuid4().hex


def require_field(body: JsonDict, field: str) -> str | ResponseReturnValue:
    """The stripped-non-empty string at `body[field]`, or a 400 naming `field`."""
    value = body.get(field)
    if not isinstance(value, str) or not value.strip():
        return errors.error_response(400, f"{field} is required")
    return value


def require_version(body: JsonDict) -> int | ResponseReturnValue:
    value = body.get("version")
    # `bool` is a subclass of `int`; `version: true` must not read as 1.
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return errors.error_response(400, "version must be an integer >= 1")
    return value


def require_state(body: JsonDict) -> TrackerState | ResponseReturnValue:
    value = body.get("state")
    if value not in _ACCEPTED_STATES:
        return errors.error_response(400, f"state must be one of: {', '.join(_ACCEPTED_STATES)}")
    return TrackerState(value)


def require_fact_kind(body: JsonDict) -> FactKind | ResponseReturnValue:
    value = body.get("kind")
    if value not in _ACCEPTED_FACT_KINDS:
        return errors.error_response(400, f"kind must be one of: {', '.join(_ACCEPTED_FACT_KINDS)}")
    return FactKind(value)


def optional_text(body: JsonDict, field: str) -> str | None:
    """The string at `body[field]`, or `None` when it is absent or not one.

    Pair it with `reject_bad_optional`, which is what turns "present and not a
    string" into a 400: this function only reads, so a handler never has to
    tell a value apart from an error response.
    """
    value = body.get(field)
    return value if isinstance(value, str) and value.strip() else None


def reject_bad_optional(
    body: JsonDict, field: str, allowed: frozenset[str] | None = None
) -> ResponseReturnValue | None:
    """`None` when `body[field]` is absent, null, or acceptable; a 400 otherwise.

    Returns the error rather than the value, because these fields are optional
    and `None` is a legitimate answer: a function returning `str | None |
    ResponseReturnValue` would leave every handler guessing which of the three
    it holds.

    `allowed` is the domain's own set when the field is a closed one. The
    check is repeated here rather than left to `Project.__post_init__` only
    because the domain's `ValueError` reaches `run_use_case` as a 500, and a
    misspelled format is a request the client can fix.
    """
    value = body.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return errors.error_response(400, f"{field} must be a non-empty string or null")
    if allowed is not None and value not in allowed:
        return errors.error_response(400, f"{field} must be one of: {', '.join(sorted(allowed))}")
    return None


def resolve_jurisdiction(code: str) -> Jurisdiction | ResponseReturnValue:
    """A `Jurisdiction`, or a 400 naming the code that matched none."""
    try:
        return jurisdiction_for(code)
    except UnknownJurisdiction as error:
        return errors.error_response(400, str(error))
