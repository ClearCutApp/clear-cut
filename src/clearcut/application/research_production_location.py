"""Run cited research for one saved location; never grant clearance."""

from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from clearcut.application.local_research_ports import LocalResearchStore
from clearcut.application.ports import GroundedAnswer, WebGrounding
from clearcut.application.team_ports import ProductionSettings
from clearcut.domain.errors import EnrichmentMissing, SourceUnavailable
from clearcut.domain.jurisdiction import jurisdiction_for
from clearcut.domain.workspace import InvalidWorkspace, WorkspaceConflict


def official_local_source(uri: str) -> bool:
    try:
        parsed = urlsplit(uri)
        if (
            parsed.scheme != "https"
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            return False
        host = (parsed.hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    # Local authorities can use named municipal domains; this conservative list
    # is extended only with reviewed provenance, never from a model's assertion.
    domains = (
        "gob.ar",
        "gob.mx",
        "gov.co",
        "gov",
        "gc.ca",
        "madrid.es",
        "toronto.ca",
        "buenosaires.gob.ar",
        "boe.es",
    )
    return any(host == domain or host.endswith("." + domain) for domain in domains)


class ResearchProductionLocation:
    def __init__(
        self, settings: ProductionSettings, store: LocalResearchStore, web: WebGrounding
    ) -> None:
        self.settings, self.store, self.web = settings, store, web

    def execute(
        self,
        project_id: str,
        actor: str,
        research_id: str,
        expected_settings_version: int,
        location_index: int,
        question: str,
        at: datetime,
    ) -> dict[str, Any]:
        settings = self.settings.get(project_id)
        if settings.version != expected_settings_version:
            raise WorkspaceConflict("reload saved production settings before researching")
        if (
            not 0 <= location_index < len(settings.locations)
            or not 1 <= len(question.strip()) <= 2000
        ):
            raise InvalidWorkspace(
                "choose a saved location and a question of at most 2000 characters"
            )
        location = settings.locations[location_index]
        query = (
            f"Production location: {location.location}, {location.country}. "
            f"Question: {question.strip()}. Find current official local authority sources. "
            "Quote the applicable passage and date. Do not infer permits, fees or legal clearance "
            "when the official evidence is missing."
        )
        try:
            result = self.web.search(query, jurisdiction_for(location.country))
            citations = tuple(
                c for c in result.citations if official_local_source(c.uri) and c.snippet.strip()
            )[:20]
        except EnrichmentMissing:
            citations = ()
        if any(
            len(c.snippet) > 20_000 or len(c.title) > 1000 or len(c.uri) > 2048 for c in citations
        ):
            raise SourceUnavailable("local research response exceeds supported evidence limits")
        # Expose only retained quoted evidence, never unsupported provider prose
        # left over after source filtering.
        answer = GroundedAnswer(
            text="\n\n".join(c.snippet for c in citations)
            if citations
            else (
                "No official local evidence found. "
                "Permit requirements, authority and fees remain unknown."
            ),
            citations=citations,
        )
        return self.store.save(
            project_id,
            actor,
            research_id,
            expected_settings_version,
            location_index,
            question.strip(),
            answer,
            at,
        )
