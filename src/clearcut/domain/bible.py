"""The project bible: cited facts an analysis checks continuity and policy against."""

import enum
from dataclasses import dataclass


class FactKind(enum.StrEnum):
    LORE = "LORE"
    POLICY = "POLICY"


@dataclass(frozen=True)
class BibleFact:
    fact_id: str
    kind: FactKind
    text: str
    source: str

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("BibleFact.text must not be blank")
        if not self.source.strip():
            raise ValueError("BibleFact.source must not be blank")


@dataclass(frozen=True)
class ProjectBible:
    project_id: str
    facts: tuple[BibleFact, ...] = ()

    def __post_init__(self) -> None:
        seen_ids: set[str] = set()
        for fact in self.facts:
            if fact.fact_id in seen_ids:
                raise ValueError(f"duplicate fact_id: {fact.fact_id}")
            seen_ids.add(fact.fact_id)

    def facts_of(self, kind: FactKind) -> tuple[BibleFact, ...]:
        return tuple(fact for fact in self.facts if fact.kind == kind)
