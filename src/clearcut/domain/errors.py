"""Domain-level errors.

`domain/` never raises a third-party or stdlib exception whose type leaks an
implementation detail (`KeyError` for a missing lookup, for example) across
its own boundary — see AGENT.md Section 5.
"""


class UnknownJurisdiction(Exception):
    """Raised when a jurisdiction code has no matching `Jurisdiction`."""

    def __init__(self, code: str) -> None:
        super().__init__(f"unknown jurisdiction code: {code!r}")
        self.code = code


class RecordNotFound(Exception):
    """The record asked for does not exist -- the caller reports "not found"
    (a 404 at the HTTP boundary) rather than a general failure."""


class SourceUnavailable(Exception):
    """An external source could not answer and the request cannot continue
    without it -- the caller treats this as a hard failure of the request (a
    502 at the HTTP boundary)."""


class EnrichmentMissing(Exception):
    """A source answered and had nothing to add for this input -- the caller
    continues without the enrichment rather than failing the request."""
