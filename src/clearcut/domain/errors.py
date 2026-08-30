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
