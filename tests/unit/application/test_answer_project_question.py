"""Unit tests for `AnswerProjectQuestion` (CP-027).

Hand-written fakes for all three ports (AGENT.md Section 5) — no
`unittest.mock`, no network. `NoGroundedSource` is imported from its adapter
module for realism only; that import is legal here because the layer guard
(`tests/unit/test_layer_boundaries.py`) restricts `src/clearcut/application`,
not `tests/`.
"""

from clearcut.adapters.gcp.vertex_search import NoGroundedSource
from clearcut.application.answer_project_question import (
    AnswerProjectQuestion,
    _names_legal_topic,
)
from clearcut.application.ports import GroundedAnswer
from clearcut.domain.bible import BibleFact, FactKind
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


class _RecordingTrackerStore:
    """A hand-written `TrackerStore` that records `latest_for_project` calls."""

    def __init__(self, items: list[TrackerItem]) -> None:
        self._items = items
        self.calls: list[str] = []

    def save(self, items: list[TrackerItem]) -> None:
        return None

    def latest(self, item_id: str) -> TrackerItem:
        raise KeyError(item_id)

    def latest_for_project(self, project_id: str) -> list[TrackerItem]:
        self.calls.append(project_id)
        return list(self._items)

    def record_script(self, script: Script) -> None:
        return None

    def latest_script(self, project_id: str) -> Script | None:
        return None


def _blocked_item() -> TrackerItem:
    return TrackerItem(
        item_id="ITEM-1",
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
        lore=FakeLoreStore(), grounding=grounding, tracker=_RecordingTrackerStore([])
    )
    question = "What does Mexican copyright law say about the mural?"

    answer = use_case.execute("proj-1", question, _MEXICO)

    assert grounding.calls == [(question, _MEXICO)]
    assert answer.citations == (citation,)
    assert "Mexican copyright law protects..." in answer.text


def test_a_non_legal_question_never_calls_grounding() -> None:
    grounding = _RecordingLegalGrounding(GroundedAnswer(text="unused", citations=()))
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(), grounding=grounding, tracker=_RecordingTrackerStore([])
    )

    use_case.execute("proj-1", "Who appears in scene 4?", _MEXICO)

    assert grounding.calls == []


def test_names_legal_topic_true_and_false_branches() -> None:
    assert _names_legal_topic("What does Mexican copyright law say about this?") is True
    assert _names_legal_topic("Who is in scene 4?") is False


def test_a_territory_blocker_question_reads_tracker_and_names_blocked_items() -> None:
    tracker = _RecordingTrackerStore([_blocked_item(), _cleared_item()])
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RecordingLegalGrounding(GroundedAnswer(text="", citations=())),
        tracker=tracker,
    )

    answer = use_case.execute("proj-1", "What is still blocking release in Mexico?", _MEXICO)

    assert tracker.calls == ["proj-1"]
    assert "ITEM-1" in answer.text
    assert "ITEM-2" not in answer.text


def test_a_non_blocker_question_never_calls_tracker() -> None:
    tracker = _RecordingTrackerStore([_blocked_item()])
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RecordingLegalGrounding(GroundedAnswer(text="", citations=())),
        tracker=tracker,
    )

    use_case.execute("proj-1", "Who appears in scene 4?", _MEXICO)

    assert tracker.calls == []


def test_a_project_with_no_indexed_facts_says_so_with_zero_citations() -> None:
    use_case = AnswerProjectQuestion(
        lore=FakeLoreStore(),
        grounding=_RecordingLegalGrounding(GroundedAnswer(text="", citations=())),
        tracker=_RecordingTrackerStore([]),
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
        lore=lore, grounding=grounding, tracker=_RecordingTrackerStore([])
    )

    answer = use_case.execute("proj-1", question, _MEXICO)

    assert "Bible p. 12" in answer.text
    assert answer.citations == ()


class _PositionalOnlyLoreStore:
    """Parameter names differ from `LoreStore`'s, so a keyword call fails."""

    def index(self, a: str, b: list[BibleFact | Scene]) -> None:
        raise NotImplementedError

    def search(self, a: str, b: str, c: int) -> list[BibleFact]:
        return []


class _PositionalOnlyLegalGrounding:
    """Parameter names differ from `LegalGrounding`'s, so a keyword call fails."""

    def ground(self, a: str, b: Jurisdiction) -> GroundedAnswer:
        return GroundedAnswer(text="grounded", citations=())


class _PositionalOnlyTrackerStore:
    """Parameter names differ from `TrackerStore`'s, so a keyword call fails."""

    def save(self, a: list[TrackerItem]) -> None:
        return None

    def latest(self, a: str) -> TrackerItem:
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
    )

    answer = use_case.execute(
        "proj-1", "What does copyright law say about blocking release?", _MEXICO
    )

    assert "grounded" in answer.text
