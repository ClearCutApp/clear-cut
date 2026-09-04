"""The Project aggregate: the top-level container a script, bible and tracker
belong to (docs/plan/sdd.md Section 2)."""

from dataclasses import dataclass

from .jurisdiction import jurisdiction_for


@dataclass(frozen=True, slots=True)
class Project:
    project_id: str
    title: str
    jurisdiction_code: str
    created_at: str

    def __post_init__(self) -> None:
        if not self.project_id.strip():
            raise ValueError("project_id must not be blank")
        if not self.title.strip():
            raise ValueError("title must not be blank")
        jurisdiction_for(self.jurisdiction_code)
