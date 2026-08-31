"""Answers a project question from bible facts, legal grounding, and tracker
state (docs/plan/sdd.md Section 3, Section 4.2; docs/plan/agentic-workflow.md
Section 6).

No in-process free-text generation, so no fourth port (AGENT.md Section 4,
CHECKPOINTS.md Decision D12): `LegalGrounding` already returns Vertex AI
Search's own grounded, cited natural-language answer, so this use case only
retrieves what its three ports return and composes it.
"""

import re
from dataclasses import dataclass, field

from clearcut.application.ports import LegalGrounding, LoreStore, TrackerStore
from clearcut.domain.bible import BibleFact
from clearcut.domain.errors import EnrichmentMissing
from clearcut.domain.finding import Citation
from clearcut.domain.jurisdiction import Jurisdiction
from clearcut.domain.tracker import TrackerItem, TrackerState

# How many bible facts to retrieve per question. Never varied, so it is a
# constant, not constructor config (AGENT.md Section 4).
_SEARCH_LIMIT = 5

_NOTHING_INDEXED = "I have nothing indexed for this project."

# Grounding every question, including "who is in scene 4", spends a Vertex
# AI Search call on something with no legal content (docs/plan/sdd.md
# Section 4.2).
#
# Stems, not whole words (CHECKPOINTS.md Decision D25): CP-027's reviewer
# measured this vocabulary against `docs/plan/agentic-workflow.md` Section
# 6's own examples and found it missed "permission" (only "permit" was
# listed), "cleared" (only "clearance" was listed), and the canonical "Can we
# show the mural in scene 12?" outright, which names no legal word in any
# form. A false positive here costs one Vertex AI Search call; a false
# negative costs the Q&A demo beat, so the stems below also reach the
# depiction verbs a clearance question is often phrased with -- what a scene
# proposes to *do* with an asset, not just its legal name.
_LEGAL_TOPIC_STEMS = frozenset(
    {
        "law",
        "legal",
        "licen",  # license, licence, licensing, licensed
        "copyright",
        "trademark",
        "statute",
        "regulat",  # regulation, regulate, regulatory
        "permi",  # permit, permitted, permission
        "right",  # rights
        "clear",  # clear, cleared, clearance
        "show",
        "use",
        "depict",
        "feature",
        "display",
    }
)

_BLOCKER_WORDS = frozenset({"blocked", "blocking", "blocker", "blockers", "outreach", "status"})

_WORD = re.compile(r"[a-z']+")


def _words(question: str) -> set[str]:
    return set(_WORD.findall(question.lower()))


def _names_legal_topic(question: str) -> bool:
    """Whether `question` is worth a Vertex AI Search call (SDD Section 4.2)."""
    stems = tuple(_LEGAL_TOPIC_STEMS)
    return any(word.startswith(stems) for word in _words(question))


def _asks_about_blockers(question: str) -> bool:
    """Whether `question` is about territory blockers or outreach status."""
    return bool(_words(question) & _BLOCKER_WORDS)


def _blocker_text(asked: bool, jurisdiction: Jurisdiction, blocked: tuple[TrackerItem, ...]) -> str:
    """Names the territory a blocker answer covers (CHECKPOINTS.md Decision D26).

    `TrackerItem` carries no jurisdiction, so this states the one territory a
    run actually covers instead of implying a per-item filter it cannot
    express -- for a blocked item and for an empty result alike.
    """
    if not asked:
        return ""
    if not blocked:
        return f"Nothing is blocked in {jurisdiction.display_name}."
    names = ", ".join(f"{item.item_id} ({item.required_document})" for item in blocked)
    return f"Blocked in {jurisdiction.display_name}: {names}"


def _compose_text(facts: tuple[BibleFact, ...], grounded_text: str, blocker_text: str) -> str:
    parts: list[str] = []
    if facts:
        parts.append("\n".join(f"{fact.text} (source: {fact.source})" for fact in facts))
    if grounded_text:
        parts.append(grounded_text)
    if blocker_text:
        parts.append(blocker_text)
    return "\n\n".join(parts) if parts else _NOTHING_INDEXED


@dataclass(frozen=True)
class ProjectAnswer:
    """An `AnswerProjectQuestion` answer: its text, the facts, and the citations behind it."""

    text: str
    facts: tuple[BibleFact, ...] = field(default_factory=tuple)
    citations: tuple[Citation, ...] = field(default_factory=tuple)


class AnswerProjectQuestion:
    """`AnswerProjectQuestion(lore, grounding, tracker)` (SDD Section 3)."""

    def __init__(self, lore: LoreStore, grounding: LegalGrounding, tracker: TrackerStore) -> None:
        self._lore = lore
        self._grounding = grounding
        self._tracker = tracker

    def execute(self, project_id: str, question: str, jurisdiction: Jurisdiction) -> ProjectAnswer:
        facts = tuple(self._lore.search(project_id, question, _SEARCH_LIMIT))
        grounded_text, citations = self._ground_if_legal(question, jurisdiction)
        asked = _asks_about_blockers(question)
        blocked = self._blocked_items_if_asked(project_id, asked)
        blocker_text = _blocker_text(asked, jurisdiction, blocked)
        text = _compose_text(facts, grounded_text, blocker_text)
        return ProjectAnswer(text=text, facts=facts, citations=citations)

    def _ground_if_legal(
        self, question: str, jurisdiction: Jurisdiction
    ) -> tuple[str, tuple[Citation, ...]]:
        if not _names_legal_topic(question):
            return "", ()
        try:
            grounded = self._grounding.ground(question, jurisdiction)
        except EnrichmentMissing:
            # `NoGroundedSource` (adapters/gcp/vertex_search.py) subclasses
            # `EnrichmentMissing` (domain/errors.py, CHECKPOINTS.md Decision
            # D23) — a name this layer may catch without importing
            # `clearcut.adapters` (AGENT.md Section 2). Grounding is optional
            # enrichment: this degrades to the bible-only answer rather than
            # failing the whole request. Any other exception is a bug, not a
            # missing enrichment, and propagates.
            return "", ()
        return grounded.text, grounded.citations

    def _blocked_items_if_asked(self, project_id: str, asked: bool) -> tuple[TrackerItem, ...]:
        if not asked:
            return ()
        items = self._tracker.latest_for_project(project_id)
        return tuple(item for item in items if item.state == TrackerState.BLOCKED)
