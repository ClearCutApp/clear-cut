"""Jurisdiction value object and the ten jurisdictions ClearCut supports.

`corpus_prefix` values mirror the folder layout under
`gs://clearcut-legal-corpus/` (docs/plan/infrastructure.md Section 2): Argentina,
United States, Spain, and Mexico are given there explicitly (`argentina/`,
`usa/`, `spain/`, `mexico/`); the remaining six follow the same common-name
convention.
"""

from dataclasses import dataclass

from .errors import UnknownJurisdiction


@dataclass(frozen=True, slots=True)
class Jurisdiction:
    code: str
    display_name: str
    corpus_prefix: str


JURISDICTIONS: tuple[Jurisdiction, ...] = (
    Jurisdiction("AR", "Argentina", "argentina/"),
    Jurisdiction("US", "United States", "usa/"),
    Jurisdiction("ES", "Spain", "spain/"),
    Jurisdiction("MX", "Mexico", "mexico/"),
    Jurisdiction("CA", "Canada", "canada/"),
    Jurisdiction("FR", "France", "france/"),
    Jurisdiction("GB", "United Kingdom", "uk/"),
    Jurisdiction("IN", "India", "india/"),
    Jurisdiction("BR", "Brazil", "brazil/"),
    Jurisdiction("KR", "South Korea", "south_korea/"),
)

_BY_CODE: dict[str, Jurisdiction] = {j.code: j for j in JURISDICTIONS}


def jurisdiction_for(code: str) -> Jurisdiction:
    """Look up a jurisdiction by its ISO 3166-1 alpha-2 code.

    Raises `UnknownJurisdiction` rather than `KeyError`, so a bad code fails
    with a domain error a caller can catch without knowing this is a dict.
    """
    try:
        return _BY_CODE[code]
    except KeyError:
        raise UnknownJurisdiction(code) from None
