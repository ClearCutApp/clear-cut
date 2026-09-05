"""Tests for the three rules ADR 0015 gives `spans_for`.

Each rule gets its own test, because each is a decision someone could
reasonably have taken the other way: mark one occurrence or all of them, nest
two overlapping marks or pick one, treat a phrase the scene does not contain
as an error or as an ordinary outcome.

The first group pins `_normalized_with_origins` against `normalize_text`
itself. That helper exists only because a regex substitution reports no
offsets, so the day the two disagree is the day every highlight lands in the
wrong place, silently.
"""

from typing import Any

import pytest

from clearcut.domain.finding import Category, Finding, NerLabel, RiskLevel
from clearcut.domain.highlight import Span, spans_for
from clearcut.domain.highlight import _normalized_with_origins as normalized_with_origins
from clearcut.domain.script import Scene, normalize_text


def _scene(text: str, number: int = 1) -> Scene:
    return Scene(number=number, heading="INT. BAR - NIGHT", page_start=1, page_end=1, text=text)


def _finding(raw_text: str, **overrides: Any) -> Finding:
    fields: dict[str, Any] = dict(
        finding_id="EVT-001",
        scene_number=1,
        page=1,
        raw_text=raw_text,
        category=Category.INDUSTRIAL_PROPERTY,
        ner_label=NerLabel.BRAND,
        risk_level=RiskLevel.MEDIUM,
        required_document="Trademark Use Authorization",
    )
    fields.update(overrides)
    return Finding(**fields)


# ---------------------------------------------------------------------------
# The offset map agrees with the normalization rule it carries offsets for.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "A Coca-Cola sign flickers.",
        "  leading and trailing  ",
        "collapsed\n\n\tinner   whitespace",
        "MiXeD CaSe",
        "",
        "   ",
        "\ttabs\tand\nnewlines\n",
        "acentuación y ñ",
    ],
)
def test_the_offset_map_reproduces_normalize_text_exactly(text: str) -> None:
    normalized, origins = normalized_with_origins(text)

    assert normalized == normalize_text(text)
    assert len(origins) == len(normalized)


@pytest.mark.parametrize(
    "text",
    ["A Coca-Cola sign flickers.", "collapsed\n\n\tinner   whitespace", "  padded  "],
)
def test_every_offset_points_at_the_character_it_came_from(text: str) -> None:
    """A non-space normalized character is the lowercased original at its
    origin. Whitespace is exempt: a run collapses to one space anchored at
    its first character, which may itself have been a tab or a newline."""
    normalized, origins = normalized_with_origins(text)

    for character, origin in zip(normalized, origins, strict=True):
        if character != " ":
            assert text[origin].lower() == character


# ---------------------------------------------------------------------------
# Rule 1: every occurrence of a repeated phrase gets a span.
# ---------------------------------------------------------------------------


def test_a_phrase_named_three_times_is_marked_three_times() -> None:
    """Coca-Cola named three times is flagged three times; picking the first
    would silently hide two."""
    text = "Coca-Cola on the wall, Coca-Cola on the bar, Coca-Cola in his hand."
    scene = _scene(text)

    spans = spans_for(scene, [_finding("Coca-Cola")])

    assert len(spans) == 3
    assert [text[span.start : span.end] for span in spans] == ["Coca-Cola"] * 3
    assert [span.start for span in spans] == sorted(span.start for span in spans)


def test_a_span_indexes_the_scene_text_the_browser_renders_not_the_normalized_one() -> None:
    """The match runs over the normalized text; the offsets come back to the
    original. A span that indexed the normalized string would slice the wrong
    characters out of anything with capitals or a collapsed whitespace run."""
    text = "The   NEON  sign reads   CocaCola   above the bar."
    scene = _scene(text)

    spans = spans_for(scene, [_finding("cocacola")])

    assert len(spans) == 1
    assert text[spans[0].start : spans[0].end] == "CocaCola"


def test_a_phrase_whose_words_are_split_across_a_line_break_still_matches() -> None:
    """`normalize_text` collapses the break, so the phrase is one string on
    both sides of the comparison; the span still covers the original run."""
    text = "a Coca-Cola\n   sign flickers"
    scene = _scene(text)

    spans = spans_for(scene, [_finding("Coca-Cola sign")])

    assert len(spans) == 1
    assert text[spans[0].start : spans[0].end] == "Coca-Cola\n   sign"


def test_the_span_carries_the_scenes_number_and_the_findings_id_and_risk() -> None:
    scene = _scene("A Coca-Cola sign flickers.", number=12)

    spans = spans_for(
        scene, [_finding("Coca-Cola", finding_id="EVT-014", risk_level=RiskLevel.HIGH)]
    )

    assert spans == (
        Span(scene_number=12, start=2, end=11, finding_id="EVT-014", risk=RiskLevel.HIGH),
    )


def test_findings_from_other_scenes_are_marked_where_their_phrase_appears() -> None:
    """Deduplication collapses an asset named in several scenes into one
    finding carrying one `scene_number`. Filtering on it would leave every
    scene but that one unmarked for an asset that is plainly there."""
    scene = _scene("A Coca-Cola sign flickers.", number=41)

    spans = spans_for(scene, [_finding("Coca-Cola", scene_number=12)])

    assert len(spans) == 1
    assert spans[0].scene_number == 41


# ---------------------------------------------------------------------------
# Rule 2: overlapping spans resolve to the higher-risk finding.
# ---------------------------------------------------------------------------


def test_two_findings_claiming_the_same_characters_leave_the_higher_risk_one() -> None:
    scene = _scene("A Coca-Cola sign flickers.")
    low = _finding("Coca-Cola", finding_id="EVT-001", risk_level=RiskLevel.LOW)
    critical = _finding(
        "Coca-Cola sign",
        finding_id="EVT-002",
        risk_level=RiskLevel.CRITICAL,
        category=Category.COPYRIGHT_WORKS,
        ner_label=NerLabel.ART_LIT,
    )

    spans = spans_for(scene, [low, critical])

    assert [span.finding_id for span in spans] == ["EVT-002"]


def test_the_loser_of_an_overlap_keeps_the_occurrences_that_do_not_overlap() -> None:
    """Losing one range is not losing the finding: the same phrase elsewhere
    in the scene is still marked."""
    scene = _scene("A Coca-Cola sign flickers. Coca-Cola again, alone.")
    low = _finding("Coca-Cola", finding_id="EVT-001", risk_level=RiskLevel.LOW)
    high = _finding("Coca-Cola sign", finding_id="EVT-002", risk_level=RiskLevel.HIGH)

    spans = spans_for(scene, [low, high])

    assert [span.finding_id for span in spans] == ["EVT-002", "EVT-001"]


def test_no_two_returned_spans_overlap_and_they_ascend_by_start() -> None:
    scene = _scene("Coca-Cola sign, Pepsi sign, Coca-Cola sign again.")
    findings = [
        _finding("Coca-Cola", finding_id="EVT-001", risk_level=RiskLevel.MEDIUM),
        _finding("Coca-Cola sign", finding_id="EVT-002", risk_level=RiskLevel.CRITICAL),
        _finding("Pepsi", finding_id="EVT-003", risk_level=RiskLevel.LOW),
        _finding("sign", finding_id="EVT-004", risk_level=RiskLevel.HIGH),
    ]

    spans = spans_for(scene, findings)

    starts = [span.start for span in spans]
    assert starts == sorted(starts)
    for earlier, later in zip(spans, spans[1:], strict=False):
        assert earlier.end <= later.start


def test_an_equal_risk_overlap_resolves_the_same_way_on_every_run() -> None:
    """Risk alone cannot break every tie, and a coin flip here would make one
    reader's highlight disagree with another's. Position then id decides."""
    scene = _scene("A Coca-Cola sign flickers.")
    first = _finding("Coca-Cola sign", finding_id="EVT-001", risk_level=RiskLevel.HIGH)
    second = _finding("sign flickers", finding_id="EVT-002", risk_level=RiskLevel.HIGH)

    forwards = spans_for(scene, [first, second])
    backwards = spans_for(scene, [second, first])

    assert forwards == backwards
    assert [span.finding_id for span in forwards] == ["EVT-001"]


# ---------------------------------------------------------------------------
# Rule 3: a raw_text the scene does not contain yields no span, and that is
# not an error.
# ---------------------------------------------------------------------------


def test_a_phrase_the_scene_does_not_contain_yields_no_span_and_does_not_raise() -> None:
    """The model paraphrased, or the scene changed between versions. The
    finding still appears in the rail; only the inline mark is absent."""
    scene = _scene("A Coca-Cola sign flickers.")

    spans = spans_for(scene, [_finding("a fizzy drink advertisement")])

    assert spans == ()


def test_a_finding_that_matches_survives_alongside_one_that_does_not() -> None:
    scene = _scene("A Coca-Cola sign flickers.")
    matches = _finding("Coca-Cola", finding_id="EVT-001")
    misses = _finding("Pepsi", finding_id="EVT-002")

    spans = spans_for(scene, [matches, misses])

    assert [span.finding_id for span in spans] == ["EVT-001"]


def test_a_blank_raw_text_yields_no_span_rather_than_marking_everything() -> None:
    """An empty needle is found at every position by a naive search, which
    would paint the whole scene."""
    scene = _scene("A Coca-Cola sign flickers.")

    assert spans_for(scene, [_finding("   ")]) == ()


def test_a_scene_with_no_findings_yields_no_spans() -> None:
    assert spans_for(_scene("A Coca-Cola sign flickers."), []) == ()


def test_an_empty_scene_yields_no_spans() -> None:
    assert spans_for(_scene(""), [_finding("Coca-Cola")]) == ()


# ---------------------------------------------------------------------------
# Span's own invariants.
# ---------------------------------------------------------------------------


def test_a_span_refuses_an_end_that_is_not_past_its_start() -> None:
    """An empty range is a mark with nothing under it; the wire contract says
    `end` is always greater than `start`."""
    with pytest.raises(ValueError, match="end"):
        Span(scene_number=1, start=4, end=4, finding_id="EVT-001", risk=RiskLevel.LOW)


def test_a_span_refuses_a_negative_start() -> None:
    with pytest.raises(ValueError, match="start"):
        Span(scene_number=1, start=-1, end=2, finding_id="EVT-001", risk=RiskLevel.LOW)
