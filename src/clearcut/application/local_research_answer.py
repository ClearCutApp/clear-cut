"""Local questions require recorded project evidence, never national-corpus inference."""

import re

from clearcut.application.local_research_ports import LocalResearchStore
from clearcut.application.ports import GroundedAnswer
from clearcut.application.team_ports import ProductionSettings
from clearcut.domain.finding import Citation

_LOCAL = re.compile(
    r"\b(street|road|sidewalk|plaza|municipal|local permit|film permit|location permit|"
    r"calle|carretera|v[ií]a p[uú]blica|permiso de rodaje|permiso local|cierre vial)\b",
    re.I,
)


def local_question(question: str) -> bool:
    return bool(_LOCAL.search(question))


class LocalResearchAnswer:
    def __init__(self, settings: ProductionSettings, store: LocalResearchStore) -> None:
        self.settings, self.store = settings, store

    def answer(self, project_id: str, question: str) -> GroundedAnswer:
        settings = self.settings.get(project_id)
        records = [
            r
            for r in self.store.list(project_id)
            if r["settings_version"] == settings.version and r["status"] == "evidence_found"
        ]
        # Exact question matching prevents an unrelated recorded permit from
        # becoming an apparent answer to a new location or different activity.
        normalized = " ".join(question.casefold().split())
        matched = [r for r in records if " ".join(r["question"].casefold().split()) == normalized]
        if not matched:
            return GroundedAnswer(
                "Local coverage gap: no matching official research is recorded for this question "
                "and the current production locations. Exact permit requirements, issuing "
                "authority and fees remain unknown. Save the locations and research this "
                "question in Production settings. "
                "National statutes do not establish local permission."
            )
        citations = tuple(Citation(**c) for record in matched for c in record["citations"])
        text = "\n\n".join(
            f"Recorded research for {r['location']['location']} ({r['created_at']}):\n{r['text']}"
            for r in matched
        )
        return GroundedAnswer(
            text + "\n\nThese are recorded source excerpts, not confirmed clearance. "
            "Check current applicability, requirements and exceptions with the issuing authority.",
            citations,
        )
