"""Unit tests for `AnswerProjectQuestion` (CP-027, CP-034).

Hand-written fakes for all four ports (AGENT.md Section 5) — no
`unittest.mock`, no network. `NoGroundedSource` and `NoWebEvidence` are
imported from their adapter modules for realism only; those imports are legal
here because the layer guard (`tests/unit/test_layer_boundaries.py`) restricts
`src/clearcut/application`, not `tests/`.
"""

import pytest

from clearcut.adapters.gcp.vertex_search import NoGroundedSource
from clearcut.adapters.parallel.search import NoWebEvidence
from clearcut.application.answer_project_question import (
    AnswerProjectQuestion,
    _names_legal_topic,
)
from clearcut.application.ports import GroundedAnswer
from clearcut.domain.bible import BibleFact, FactKind
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.finding import Citation
from clearcut.domain.jurisdiction import Jurisdiction, jurisdiction_for
from clearcut.domain.script import Scene, Script
from clearcut.domain.tracker import TrackerItem, TrackerState
from tests.unit.fakes import FakeLoreStore

_MEXICO = jurisdiction_for("MX")


class _RecordingLegalGrounding:
    """Records every call, so a test can assert it ran zero or one times."""

    def __init__(self, answer: GroundedAnswer) -> None:
        self._answer = answer
        self.calls: list[tuple[str, Jurisdiction]] = []

    def ground(self, query: str, jurisdiction: Jurisdiction) -> GroundedAnswer:
        self.calls.append((query, jurisdiction))
        return self._answer


class _RaisingLegalGrounding:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def ground(self, query: str, jurisdiction: Jurisdiction) -> GroundedAnswer:
        raise self._error


class _RecordingWebGrounding:
    """Records every call, so the cost guard can assert it ran zero times."""

    def __init__(self, answer: GroundedAnswer) -> None:
        self._answer = answer
        self.calls: list[tuple[str, Jurisdiction]] = []

    def search(self, question: str, jurisdiction: Jurisdiction) -> GroundedAnswer:
        self.calls.append((question, jurisdiction))
        return self._answer


class _RaisingWebGrounding:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def search(self, question: str, jurisdiction: Jurisdiction) -> GroundedAnswer:
        raise self._error


def _silent_web() -> _RecordingWebGrounding:
    """A `WebGrounding` that answers with nothing.

    Every test written before the web fallback existed passes one of these:
    the corpus tests that already return citations never reach it, and the
    ones that do reach it get an empty answer, so their assertions still
    describe the corpus path alone.
    """
    return _RecordingWebGrounding(GroundedAnswer(text="", citations=()))


class _RecordingTrackerStore:
    """A hand-written `TrackerStore` that records `latest_for_project` calls."""

    def __init__(self, items: list[TrackerItem]) -> None:
        self._items = items
        self.calls: list[str] = []

    def save(self, items: list[TrackerItem]) -> None:
        return None

    def latest(self, project_id: str, item_id: str) -> TrackerItem:
        raise KeyError(item_id)

    def latest_for_project(self, project_id: str) -> list[TrackerItem]:
        self.calls.append(project_id)
        return list(self._items)

    def record_script(self, script: Script) -> None:
        return None

    def latest_script(self, project_id: str) -> Script | None:
        return None


class _RaisingTrackerStore:
    """A hand-written `TrackerStore` whose `latest_for_project` raises, so a
    test can assert the exception propagates rather than reading as
    clearance."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def save(self, items: list[TrackerItem]) -> None:
        return None

    def latest(self, project_id: str, item_id: str) -> TrackerItem:
        raise KeyError(item_id)

    def latest_for_project(self, project_id: str) -> list[TrackerItem]:
        raise self._error

    def record_script(self, script: Script) -> None:
        return None

    def latest_script(self, project_id: str) -> Script | None:
        return None


def _blocked_item() -> TrackerItem:
    return TrackerItem(
        item_id="ITEM-1",
        project_id="proj-1",
        finding_id="EVT-001",
        scene_numbers=(12,),
        state=TrackerState.BLOCKED,
        required_document="Music sync license",
        contact="",
        litigation_posture="",
        note="",
        updated_at="2026-01-01T00:00:00Z",
        version=1,
    )


def _cleared_item() -> TrackerItem:
    return TrackerItem(
        item_id="ITEM-2",
        project_id="proj-1",
        finding_id="EVT-002",
        scene_numbers=(4,),
        state=TrackerState.CLEARED,
        required_document="",
        contact="",
        litigation_posture="",
        note="",
        updated_at="2026-01-01T00:00:00Z",
        version=1,
    )


def test_retrieves_bible_facts_and_their_source_appears_in_the_answer() -> None:
    lore = FakeLoreStore()
    lore.index(
        "proj-1",
        [
            BibleFact(
                fact_id="F1",
                kind=FactKind.LORE,
                text="The mural was painted in 1990.",
                source="Bible p. 12",
            )
        ],
    )
    use_case = AnswerProjectQuestion(
        lore=lore,
        grounding=_RecordingLegalGrounding(GroundedAnswer(text="", citations=())),
        tracker=_RecordingTrackerStore([]),
        web=_silent_web(),
    )

    answer = use_case.execute("proj-1", "Who painted the mural?", _MEXICO)

    assert "Bible p. 12" in answer.text
    assert answer.facts[0].source == "Bible p. 12"


def test_a_legal_topic_question_grounds_and_carries_citations() -> None:
    citation = Citation(uri="https://law.example/mx", title="Ley Federal", snippet="...")
    grounding = _RecordingLegalGrounding(
        GroundedAnswer(text="Mexican copyright law protects...", citations=(citation,))
    )
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=grounding,
        tracker=_RecordingTrackerStore([]),
        web=_silent_web(),
    )
    question = "What does Mexican copyright law say about the mural?"

    answer = use_case.execute("proj-1", question, _MEXICO)

    assert grounding.calls == [(question, _MEXICO)]
    assert answer.citations == (citation,)
    assert "Mexican copyright law protects..." in answer.text


def test_a_non_legal_question_never_calls_grounding() -> None:
    grounding = _RecordingLegalGrounding(GroundedAnswer(text="unused", citations=()))
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=grounding,
        tracker=_RecordingTrackerStore([]),
        web=_silent_web(),
    )

    use_case.execute("proj-1", "Who appears in scene 4?", _MEXICO)

    assert grounding.calls == []


def test_a_scene_roster_question_never_calls_grounding() -> None:
    """D25: the widened vocabulary must not regress CP-027's zero-call case."""
    grounding = _RecordingLegalGrounding(GroundedAnswer(text="unused", citations=()))
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=grounding,
        tracker=_RecordingTrackerStore([]),
        web=_silent_web(),
    )

    use_case.execute("proj-1", "Who is in scene 4?", _MEXICO)

    assert grounding.calls == []


def test_a_scene_count_question_never_calls_grounding() -> None:
    """D25: the widened vocabulary must not regress CP-027's zero-call case."""
    grounding = _RecordingLegalGrounding(GroundedAnswer(text="unused", citations=()))
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=grounding,
        tracker=_RecordingTrackerStore([]),
        web=_silent_web(),
    )

    use_case.execute("proj-1", "How many scenes are there?", _MEXICO)

    assert grounding.calls == []


def test_names_legal_topic_true_and_false_branches() -> None:
    assert _names_legal_topic("What does Mexican copyright law say about this?") is True
    assert _names_legal_topic("Who is in scene 4?") is False


def test_names_legal_topic_true_for_the_agentic_workflow_mural_example() -> None:
    """D25: `docs/plan/agentic-workflow.md` Section 6's own canonical example.

    No word in the sentence is a legal word in any form; it is a clearance
    question because of what it proposes to *do* with the mural, so the
    vocabulary has to reach depiction verbs, not just legal nouns.
    """
    assert _names_legal_topic("Can we show the mural in scene 12?") is True


def test_names_legal_topic_true_for_the_permission_question() -> None:
    """D25: `permission` does not share a prefix with `permit` alone."""
    assert _names_legal_topic("Do we need permission for the Coca-Cola bottle?") is True


def test_names_legal_topic_true_for_the_cleared_question() -> None:
    """D25: `cleared` is a form of `clear`, not of `clearance`."""
    assert _names_legal_topic("Is the song cleared for streaming?") is True


def test_names_legal_topic_false_for_a_scene_roster_question() -> None:
    assert _names_legal_topic("Who is in scene 4?") is False


def test_names_legal_topic_false_for_a_scene_count_question() -> None:
    assert _names_legal_topic("How many scenes are there?") is False


def test_permit_permission_and_permitted_all_match_the_same_stem() -> None:
    """D25: morphology is handled by one stem, not by enumerating inflections."""
    assert _names_legal_topic("Do we have a permit?") is True
    assert _names_legal_topic("Do we need permission?") is True
    assert _names_legal_topic("Was this permitted?") is True


def test_a_territory_blocker_question_reads_tracker_and_names_blocked_items() -> None:
    tracker = _RecordingTrackerStore([_blocked_item(), _cleared_item()])
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RecordingLegalGrounding(GroundedAnswer(text="", citations=())),
        tracker=tracker,
        web=_silent_web(),
    )

    answer = use_case.execute("proj-1", "What is still blocking release in Mexico?", _MEXICO)

    assert tracker.calls == ["proj-1"]
    assert "ITEM-1" in answer.text
    assert "ITEM-2" not in answer.text


def test_a_blocker_answer_names_the_jurisdiction_it_covers() -> None:
    """D26: `TrackerItem` carries no jurisdiction, so the answer names the one
    territory a run actually covers instead of implying a per-item filter it
    cannot express.
    """
    tracker = _RecordingTrackerStore([_blocked_item()])
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RecordingLegalGrounding(GroundedAnswer(text="", citations=())),
        tracker=tracker,
        web=_silent_web(),
    )

    answer = use_case.execute("proj-1", "What is still blocking release in Mexico?", _MEXICO)

    assert _MEXICO.display_name in answer.text


def test_a_blocker_question_with_nothing_blocked_still_names_the_territory() -> None:
    """D26 failure path: an empty result is still about a stated territory,
    not a bare "nothing found".
    """
    tracker = _RecordingTrackerStore([_cleared_item()])
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RecordingLegalGrounding(GroundedAnswer(text="", citations=())),
        tracker=tracker,
        web=_silent_web(),
    )

    answer = use_case.execute("proj-1", "What is still blocking release in Mexico?", _MEXICO)

    assert _MEXICO.display_name in answer.text
    assert answer.text != "I have nothing indexed for this project."


def test_a_blocker_question_with_no_tracker_rows_says_the_project_is_not_indexed() -> None:
    """D31: zero tracker rows must read as "not indexed", not as clearance.

    Before this checkpoint the same input answered "Nothing is blocked in
    Mexico." -- an assurance an empty table has no evidence for.
    """
    tracker = _RecordingTrackerStore([])
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RecordingLegalGrounding(GroundedAnswer(text="", citations=())),
        tracker=tracker,
        web=_silent_web(),
    )

    answer = use_case.execute("proj-1", "What is still blocking release in Mexico?", _MEXICO)

    assert tracker.calls == ["proj-1"]
    assert "not blocked" not in answer.text.lower()
    assert "nothing is blocked" not in answer.text.lower()


def test_the_unindexed_and_nothing_blocked_answers_are_distinguishable() -> None:
    """D31: a caller must be able to tell "unknown" from "cleared" -- a
    dashboard cannot render one as the other.
    """
    unindexed = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RecordingLegalGrounding(GroundedAnswer(text="", citations=())),
        tracker=_RecordingTrackerStore([]),
        web=_silent_web(),
    ).execute("proj-1", "What is still blocking release in Mexico?", _MEXICO)
    nothing_blocked = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RecordingLegalGrounding(GroundedAnswer(text="", citations=())),
        tracker=_RecordingTrackerStore([_cleared_item()]),
        web=_silent_web(),
    ).execute("proj-1", "What is still blocking release in Mexico?", _MEXICO)

    assert unindexed.text != nothing_blocked.text


def test_a_blocker_question_with_bible_facts_but_no_tracker_rows_names_the_tracker_gap() -> None:
    """D31: the tracker-scoped and whole-project "nothing indexed" texts are
    two different constants on purpose (`_TRACKER_NOT_INDEXED` vs.
    `_NOTHING_INDEXED`). A project can have bible facts indexed and zero
    tracker rows at the same time, and every other D31 test uses an empty
    `FakeLoreStore`, so none of them can tell the two constants apart -- the
    bible-empty fallback always wins and the tracker-scoped sentence is never
    the reason the assertion passes. This test indexes one bible fact so that
    fallback cannot fire, and checks the tracker-scoped sentence by name.
    """
    lore = FakeLoreStore()
    lore.index(
        "proj-1",
        [
            BibleFact(
                fact_id="F1",
                kind=FactKind.LORE,
                text="The mural was painted in 1990.",
                source="Bible p. 12",
            )
        ],
    )
    use_case = AnswerProjectQuestion(
        lore=lore,
        grounding=_RecordingLegalGrounding(GroundedAnswer(text="", citations=())),
        tracker=_RecordingTrackerStore([]),
        web=_silent_web(),
    )

    answer = use_case.execute("proj-1", "What is still blocking release in Mexico?", _MEXICO)

    assert "I have no tracker data indexed for this project." in answer.text
    assert "I have nothing indexed for this project." not in answer.text


def test_a_tracker_outage_propagates_instead_of_reading_as_clearance() -> None:
    """D31 failure path: an outage must not degrade to "nothing blocked" --
    the same defect one layer over that CP-026's reviewer flagged. The catch
    in this module is `except EnrichmentMissing` by name (D23), so
    `SourceUnavailable` is never caught here.
    """
    tracker = _RaisingTrackerStore(SourceUnavailable("tracker down"))
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RecordingLegalGrounding(GroundedAnswer(text="", citations=())),
        tracker=tracker,
        web=_silent_web(),
    )

    with pytest.raises(SourceUnavailable):
        use_case.execute("proj-1", "What is still blocking release in Mexico?", _MEXICO)


def test_a_non_blocker_question_never_calls_tracker() -> None:
    tracker = _RecordingTrackerStore([_blocked_item()])
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RecordingLegalGrounding(GroundedAnswer(text="", citations=())),
        tracker=tracker,
        web=_silent_web(),
    )

    use_case.execute("proj-1", "Who appears in scene 4?", _MEXICO)

    assert tracker.calls == []


def test_a_project_with_no_indexed_facts_says_so_with_zero_citations() -> None:
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RecordingLegalGrounding(GroundedAnswer(text="", citations=())),
        tracker=_RecordingTrackerStore([]),
        web=_silent_web(),
    )

    answer = use_case.execute("proj-1", "Who appears in scene 4?", _MEXICO)

    assert answer.text == "I have nothing indexed for this project."
    assert answer.citations == ()


def test_no_grounded_source_degrades_to_a_bible_only_answer() -> None:
    lore = FakeLoreStore()
    lore.index(
        "proj-1",
        [
            BibleFact(
                fact_id="F1",
                kind=FactKind.LORE,
                text="The mural was painted in 1990.",
                source="Bible p. 12",
            )
        ],
    )
    question = "What does Mexican copyright law say about the mural?"
    grounding = _RaisingLegalGrounding(NoGroundedSource(question))
    use_case = AnswerProjectQuestion(
        lore=lore,
        grounding=grounding,
        tracker=_RecordingTrackerStore([]),
        web=_silent_web(),
    )

    answer = use_case.execute("proj-1", question, _MEXICO)

    assert "Bible p. 12" in answer.text
    assert answer.citations == ()


def test_a_grounding_bug_propagates_instead_of_degrading_silently() -> None:
    """D23/CP-034: only `EnrichmentMissing` degrades to a bible-only answer.

    CP-027's reviewer found `except Exception` here swallowing `TypeError`,
    `AttributeError`, and `ZeroDivisionError` from `grounding.ground` as a
    silent bible-only answer. Narrowing the catch to `EnrichmentMissing`
    means a bug like this one now propagates instead.
    """
    grounding = _RaisingLegalGrounding(TypeError("boom"))
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=grounding,
        tracker=_RecordingTrackerStore([]),
        web=_silent_web(),
    )

    with pytest.raises(TypeError):
        use_case.execute("proj-1", "What does copyright law say about the mural?", _MEXICO)


class _PositionalOnlyLoreStore:
    """Parameter names differ from `LoreStore`'s, so a keyword call fails."""

    def index(self, a: str, b: list[BibleFact | Scene]) -> None:
        raise NotImplementedError

    def facts(self, a: str) -> list[BibleFact]:
        raise NotImplementedError

    def search(self, a: str, b: str, c: int) -> list[BibleFact]:
        return []


class _PositionalOnlyLegalGrounding:
    """Parameter names differ from `LegalGrounding`'s, so a keyword call fails."""

    def ground(self, a: str, b: Jurisdiction) -> GroundedAnswer:
        return GroundedAnswer(text="grounded", citations=())


class _PositionalOnlyWebGrounding:
    """Parameter names differ from `WebGrounding`'s, so a keyword call fails."""

    def search(self, a: str, b: Jurisdiction) -> GroundedAnswer:
        return GroundedAnswer(text="from the web", citations=())


class _PositionalOnlyTrackerStore:
    """Parameter names differ from `TrackerStore`'s, so a keyword call fails."""

    def save(self, a: list[TrackerItem]) -> None:
        return None

    def latest(self, a: str, b: str) -> TrackerItem:
        raise KeyError(a)

    def latest_for_project(self, a: str) -> list[TrackerItem]:
        return []

    def record_script(self, a: Script) -> None:
        return None

    def latest_script(self, a: str) -> Script | None:
        return None


def test_port_methods_are_called_positionally() -> None:
    """D15: a keyword call through any of these three fakes raises `TypeError`."""
    use_case = AnswerProjectQuestion(
        lore=_PositionalOnlyLoreStore(),
        grounding=_PositionalOnlyLegalGrounding(),
        tracker=_PositionalOnlyTrackerStore(),
        web=_PositionalOnlyWebGrounding(),
    )

    answer = use_case.execute(
        "proj-1", "What does copyright law say about blocking release?", _MEXICO
    )

    assert "grounded" in answer.text
    assert "from the web" in answer.text


# --- CP-062: the live web fallback -------------------------------------------
#
# `LegalGrounding` answers from ten hand-curated corpus prefixes, and
# `docs/plan/sdd.md` Section 9.2 records that six of the eight clearance
# categories ground against nothing. A producer asking a question the corpus
# never covered used to get bible facts and silence. These tests pin what it
# gets instead, and -- just as importantly -- when it must not cost a search.


_WEB_CITATION = Citation(
    uri="https://www.argentina.gob.ar/normativa/nacional/ley-11723-42755/texto",
    title="Ley 11.723",
    snippet="Articulo 2. El derecho de propiedad de una obra artistica...",
)
_WEB_ANSWER = GroundedAnswer(
    text="From a live web search, not ClearCut's licensed legal corpus.",
    citations=(_WEB_CITATION,),
)
_LEGAL_QUESTION = "What does Mexican copyright law say about the mural?"


def test_a_corpus_miss_falls_back_to_the_live_web_search() -> None:
    web = _RecordingWebGrounding(_WEB_ANSWER)
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RaisingLegalGrounding(NoGroundedSource(_LEGAL_QUESTION)),
        tracker=_RecordingTrackerStore([]),
        web=web,
    )

    answer = use_case.execute("proj-1", _LEGAL_QUESTION, _MEXICO)

    assert web.calls == [(_LEGAL_QUESTION, _MEXICO)]
    assert answer.citations == (_WEB_CITATION,)


def test_a_corpus_answer_with_no_citations_also_falls_back_to_the_web() -> None:
    """The condition is citations, not text.

    `adapters/gcp/vertex_search.py` can return grounded prose with an empty
    `groundingMetadata`, and `adapters/http/questions.py:26` says an answer
    with no citation is one this API does not give -- so uncited prose is a
    miss, however confident it reads.
    """
    web = _RecordingWebGrounding(_WEB_ANSWER)
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RecordingLegalGrounding(
            GroundedAnswer(text="Mexican law is broadly protective.", citations=())
        ),
        tracker=_RecordingTrackerStore([]),
        web=web,
    )

    answer = use_case.execute("proj-1", _LEGAL_QUESTION, _MEXICO)

    assert web.calls == [(_LEGAL_QUESTION, _MEXICO)]
    assert answer.citations == (_WEB_CITATION,)


def test_an_uncited_corpus_answer_is_appended_to_rather_than_replaced() -> None:
    """The corpus said something; it just could not cite it. Dropping that
    text would lose a sentence the licensed source produced."""
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RecordingLegalGrounding(
            GroundedAnswer(text="Mexican law is broadly protective.", citations=())
        ),
        tracker=_RecordingTrackerStore([]),
        web=_RecordingWebGrounding(_WEB_ANSWER),
    )

    answer = use_case.execute("proj-1", _LEGAL_QUESTION, _MEXICO)

    assert "Mexican law is broadly protective." in answer.text
    assert _WEB_ANSWER.text in answer.text


def test_a_cited_corpus_answer_never_spends_a_web_search() -> None:
    """The cost guard. The corpus is the stronger source and it answered, so
    the second network call buys nothing."""
    web = _RecordingWebGrounding(_WEB_ANSWER)
    corpus_citation = Citation(uri="https://law.example/mx", title="Ley Federal", snippet="...")
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RecordingLegalGrounding(
            GroundedAnswer(text="Mexican copyright law protects...", citations=(corpus_citation,))
        ),
        tracker=_RecordingTrackerStore([]),
        web=web,
    )

    answer = use_case.execute("proj-1", _LEGAL_QUESTION, _MEXICO)

    assert web.calls == []
    assert answer.citations == (corpus_citation,)


def test_a_non_legal_question_never_spends_a_web_search() -> None:
    web = _RecordingWebGrounding(_WEB_ANSWER)
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RecordingLegalGrounding(GroundedAnswer(text="", citations=())),
        tracker=_RecordingTrackerStore([]),
        web=web,
    )

    use_case.execute("proj-1", "Who appears in scene 4?", _MEXICO)

    assert web.calls == []


def test_no_web_evidence_degrades_to_the_bible_only_answer() -> None:
    """`NoWebEvidence` is an `EnrichmentMissing`, the one type this layer
    catches by name (D23), so a search that found nothing usable is the same
    outcome as no search at all."""
    lore = FakeLoreStore()
    lore.index(
        "proj-1",
        [
            BibleFact(
                fact_id="F1",
                kind=FactKind.LORE,
                text="The mural was painted in 1990.",
                source="Bible p. 12",
            )
        ],
    )
    use_case = AnswerProjectQuestion(
        lore=lore,
        grounding=_RaisingLegalGrounding(NoGroundedSource(_LEGAL_QUESTION)),
        tracker=_RecordingTrackerStore([]),
        web=_RaisingWebGrounding(NoWebEvidence(_LEGAL_QUESTION)),
    )

    answer = use_case.execute("proj-1", _LEGAL_QUESTION, _MEXICO)

    assert "Bible p. 12" in answer.text
    assert answer.citations == ()


def test_a_web_search_outage_propagates_instead_of_degrading_silently() -> None:
    """D23: `SourceUnavailable` is an outage, not a missing enrichment, and
    the route maps it to 502. See the comment in `_web_answer` for why this
    is deliberate rather than an oversight."""
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RaisingLegalGrounding(NoGroundedSource(_LEGAL_QUESTION)),
        tracker=_RecordingTrackerStore([]),
        web=_RaisingWebGrounding(SourceUnavailable("Parallel Search API is down")),
    )

    with pytest.raises(SourceUnavailable):
        use_case.execute("proj-1", _LEGAL_QUESTION, _MEXICO)


def test_a_web_search_bug_propagates_instead_of_degrading_silently() -> None:
    """The `EnrichmentMissing`-only catch, proved on the web port too."""
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RaisingLegalGrounding(NoGroundedSource(_LEGAL_QUESTION)),
        tracker=_RecordingTrackerStore([]),
        web=_RaisingWebGrounding(TypeError("boom")),
    )

    with pytest.raises(TypeError):
        use_case.execute("proj-1", _LEGAL_QUESTION, _MEXICO)
