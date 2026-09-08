"""The Project aggregate: the top-level container a script, bible and tracker
belong to (docs/plan/sdd.md Section 2).

`poster_uri`, `format` and `status` are the three optional presentation facts
the projects list and the project detail screen draw. They are optional
because a project created before them -- or by a client that never sends them
-- is still a project: `None` means "not set", and the frontend decides what
to draw for one. Nothing here invents a default, because a default would be
this project claiming a format nobody chose for it.

`format` and `status` are closed sets rather than free strings for the same
reason `jurisdiction_code` is: a screen that groups by them cannot group by a
value it has never heard of, and the misspelling that produces one is found
here rather than in a client.
"""

from dataclasses import dataclass

from .jurisdiction import jurisdiction_for

PROJECT_FORMATS: frozenset[str] = frozenset({"feature_film", "documentary", "series", "short"})

PROJECT_STATUSES: frozenset[str] = frozenset({"in_development", "in_production", "completed"})


def _checked_member(value: str | None, allowed: frozenset[str], field: str) -> None:
    """Refuses a non-`None` value outside `allowed`, naming the field and the
    set it had to come from.

    `None` is always valid: it is the absence of the fact, not a bad one.
    """
    if value is not None and value not in allowed:
        raise ValueError(f"unknown {field}: {value!r}; expected one of {sorted(allowed)} or None")


@dataclass(frozen=True, slots=True)
class Project:
    project_id: str
    title: str
    jurisdiction_code: str
    created_at: str
    poster_uri: str | None = None
    format: str | None = None
    status: str | None = None

    def __post_init__(self) -> None:
        if not self.project_id.strip():
            raise ValueError("project_id must not be blank")
        if not self.title.strip():
            raise ValueError("title must not be blank")
        jurisdiction_for(self.jurisdiction_code)
        _checked_member(self.format, PROJECT_FORMATS, "format")
        _checked_member(self.status, PROJECT_STATUSES, "status")
