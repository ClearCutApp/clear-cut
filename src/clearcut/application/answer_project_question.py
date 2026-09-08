"""Answers a project question from bible facts, legal grounding, and tracker
state (docs/plan/sdd.md Section 3, Section 4.2; docs/plan/agentic-workflow.md
Section 6).

No in-process free-text generation (AGENT.md Section 4, CHECKPOINTS.md
Decision D12): `LegalGrounding` already returns Vertex AI Search's own
grounded, cited natural-language answer, and `WebGrounding` returns quoted
excerpts Parallel wrote, so this use case only retrieves what its four ports
return and composes it.

The fourth port is a fallback, not a peer. `LegalGrounding` reads the
licensed corpus, whose citations are statutes ClearCut chose to trust, and it
answers first. `WebGrounding` runs only when that corpus produced no citation
at all -- which `docs/plan/sdd.md` Section 9.2 records is the common case,
six of the eight clearance categories grounding against nothing. Before this,
a producer asking a question the corpus never covered got bible facts and
silence.
"""

import re
from dataclasses import dataclass, field

from clearcut.application.current_scene_lore import CurrentSceneLore
from clearcut.application.local_research_answer import LocalResearchAnswer, local_question
from clearcut.application.ports import LegalGrounding, LoreStore, TrackerStore, WebGrounding
from clearcut.domain.bible import BibleFact
from clearcut.domain.errors import EnrichmentMissing
from clearcut.domain.finding import Citation
from clearcut.domain.jurisdiction import Jurisdiction
from clearcut.domain.tracker import TrackerItem, TrackerState

# How many bible facts to retrieve per question. Never varied, so it is a
# constant, not constructor config (AGENT.md Section 4).
_SEARCH_LIMIT = 5

_NOTHING_INDEXED = "I have nothing indexed for this project."

# CHECKPOINTS.md Decision D31: a blocker answer over a project with zero
# tracker rows must say the project is not indexed, not that nothing is
# blocked -- an assurance an empty table has no evidence for. This is the
# tracker-scoped counterpart to `_NOTHING_INDEXED`, kept separate so it never
# contradicts bible facts that may already be indexed for the same project.
_TRACKER_NOT_INDEXED = "I have no tracker data indexed for this project."

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
        "ley",
        "derech",
        "autoriza",
        "licenc",
        "mostrar",
        "usar",
        "marca",
        "reproduc",
        "protecc",
        "privaci",
        "propiedad",
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


def _blocker_text(asked: bool, jurisdiction: Jurisdiction, items: tuple[TrackerItem, ...]) -> str:
    """Names the territory a blocker answer covers (CHECKPOINTS.md Decision D26).

    Three cases, one rule -- assurance requires rows (Decision D31):

    1. no tracker rows at all -> not indexed, no clearance claim made;
    2. rows exist, none BLOCKED -> nothing is blocked in the named territory,
       an assurance the rows actually earn;
    3. rows exist, some BLOCKED -> the items are named, unchanged from D26.

    `TrackerItem` carries no jurisdiction, so cases 2 and 3 state the one
    territory a run actually covers instead of implying a per-item filter
    they cannot express.
    """
    if not asked:
        return ""
    if not items:
        return _TRACKER_NOT_INDEXED
    blocked = tuple(item for item in items if item.state == TrackerState.BLOCKED)
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
    """`AnswerProjectQuestion(lore, grounding, tracker, web)` (SDD Section 3)."""

    def __init__(
        self,
        lore: LoreStore,
        grounding: LegalGrounding,
        tracker: TrackerStore,
        web: WebGrounding,
        local: LocalResearchAnswer | None = None,
        scenes: CurrentSceneLore | None = None,
    ) -> None:
        self._lore = lore
        self._grounding = grounding
        self._tracker = tracker
        self._web = web
        self._local = local
        self._scenes = scenes

    def execute(self, project_id: str, question: str, jurisdiction: Jurisdiction) -> ProjectAnswer:
        if self._local is not None and local_question(question):
            answer = self._local.answer(project_id, question)
            return ProjectAnswer(text=answer.text, citations=answer.citations)
        facts = tuple(self._lore.search(project_id, question, _SEARCH_LIMIT))
        grounded_text, citations = self._ground_if_legal(question, jurisdiction)
        asked = _asks_about_blockers(question)
        if self._scenes is not None and not _names_legal_topic(question) and not asked:
            scene_answer = self._scenes.answer(project_id, question)
            grounded_text, citations = scene_answer.text, scene_answer.citations
        items = self._tracker_items_if_asked(project_id, asked)
        blocker_text = _blocker_text(asked, jurisdiction, items)
        text = _compose_text(facts, grounded_text, blocker_text)
        return ProjectAnswer(text=text, facts=facts, citations=citations)

    def _ground_if_legal(
        self, question: str, jurisdiction: Jurisdiction
    ) -> tuple[str, tuple[Citation, ...]]:
        """The corpus first; the live web only when the corpus cited nothing.

        The condition is citations, not text. `adapters/gcp/vertex_search.py`
        can return grounded prose with an empty `groundingMetadata`, and
        `adapters/http/questions.py:26` states the rule this branch enforces:
        an answer with no citation is an answer this API does not give. Uncited
        prose is therefore a miss, however confident it reads.
        """
        if not _names_legal_topic(question):
            return "", ()
        text, citations = self._corpus_answer(question, jurisdiction)
        if citations:
            return text, citations
        return self._web_answer(question, jurisdiction, text)

    def _corpus_answer(
        self, question: str, jurisdiction: Jurisdiction
    ) -> tuple[str, tuple[Citation, ...]]:
        try:
            grounded = self._grounding.ground(question, jurisdiction)
        except EnrichmentMissing:
            # `NoGroundedSource` (adapters/gcp/vertex_search.py) subclasses
            # `EnrichmentMissing` (domain/errors.py, CHECKPOINTS.md Decision
            # D23) — a name this layer may catch without importing
            # `clearcut.adapters` (AGENT.md Section 2). Grounding is optional
            # enrichment: this degrades to the web search below, and then to
            # the bible-only answer, rather than failing the whole request.
            # Any other exception is a bug, not a missing enrichment, and
            # propagates.
            return "", ()
        return grounded.text, grounded.citations

    def _web_answer(
        self, question: str, jurisdiction: Jurisdiction, corpus_text: str
    ) -> tuple[str, tuple[Citation, ...]]:
        """The live web search, appended to whatever the corpus managed to say.

        Appended rather than substituted: the corpus produced that sentence
        from a licensed source and only failed to cite it, so replacing it
        would throw away the stronger half of the answer.

        `SourceUnavailable` is deliberately not caught. `NoWebEvidence`
        (adapters/parallel/search.py) is an `EnrichmentMissing` and degrades
        here; `WebSearchUnavailable` is a `SourceUnavailable` and propagates
        to a 502, the same as every other adapter under D23. That is a real
        trade and worth naming: a Parallel outage now fails a question that
        used to degrade to bible facts. It is the right one, because the
        alternative is answering a clearance question from the bible alone
        while silently omitting that the legal half of it never ran — and a
        producer cannot tell that answer from one where the law had nothing
        to add.
        """
        try:
            found = self._web.search(question, jurisdiction)
        except EnrichmentMissing:
            return corpus_text, ()
        if not corpus_text:
            return found.text, found.citations
        return f"{corpus_text}\n\n{found.text}", found.citations

    def _tracker_items_if_asked(self, project_id: str, asked: bool) -> tuple[TrackerItem, ...]:
        if not asked:
            return ()
        return tuple(self._tracker.latest_for_project(project_id))
