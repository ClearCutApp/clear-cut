"""Records new bible facts (`createBibleFact`,
`POST /api/projects/{project_id}/bible/facts`).

The server assigns `fact_id`, so this use case reads the project's existing
facts to find where its sequence stands and numbers the batch from there:
a bible holding `FACT-001` given two drafts answers `FACT-002` and
`FACT-003`. `next_fact_number` (`domain/bible.py`) owns that arithmetic.

Two rules shape the order of the three steps below. An empty batch is
refused before the port is touched, because a write that writes nothing is a
mistake in the request rather than a silent success. And every `BibleFact` is
built before any of them is indexed, so a draft the domain refuses -- blank
text, blank source -- leaves the bible as it was instead of half written.
The whole batch reaches `index` in one call for the same reason.
"""

from dataclasses import dataclass

from clearcut.application.ports import LoreStore
from clearcut.domain.bible import BibleFact, FactKind, next_fact_number
from clearcut.domain.script import Scene


@dataclass(frozen=True)
class FactDraft:
    """One fact as the producer submitted it, before the server numbers it.

    Carries the three fields `BibleFactCreate` requires; `fact_id` is absent
    because the caller does not get to choose it.
    """

    kind: FactKind
    text: str
    source: str


class AddBibleFacts:
    """`AddBibleFacts(lore)`."""

    def __init__(self, lore: LoreStore) -> None:
        self._lore = lore

    def execute(self, project_id: str, drafts: list[FactDraft]) -> list[BibleFact]:
        if not drafts:
            raise ValueError("drafts must not be empty")
        first_number = next_fact_number(self._lore.facts(project_id))
        facts = [
            BibleFact(
                fact_id=f"FACT-{first_number + offset:03d}",
                kind=draft.kind,
                text=draft.text,
                source=draft.source,
            )
            for offset, draft in enumerate(drafts)
        ]
        records: list[BibleFact | Scene] = list(facts)
        self._lore.index(project_id, records)
        return facts
