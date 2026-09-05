"""Where in a scene's text each finding was raised (ADR 0015).

The Script Review screen marks the flagged text inline, the way a proofreader
marks prose, and something has to know the character range each mark covers.
`Finding` carries `raw_text`, not offsets, and the extractor is never asked
for any: an offset that is three characters wrong renders a highlight
straddling a word with no signal that anything went wrong, while a wrong
category is visibly wrong. The same reasoning that makes `taxonomy.category_for`
re-derive the category applies here, more strongly.

So the offsets are searched for rather than reported, and the search runs
here. It is a rule about what a script and its findings mean, expressed in
domain types with no I/O, and it lives on the server so an export and the
browser cannot drift apart over which of two findings wins a character range.

Matching normalizes through `script.normalize_text`, the one rule `dedupe.py`
already uses to decide two findings name the same asset. Because that rule
lowercases and collapses whitespace runs, a match found in the normalized text
has to be carried back to an offset into the text the browser renders, which
is what `_normalized_with_origins` exists for.

Three rules this module owns, each a decision rather than a rendering detail:

- A phrase that appears more than once in a scene is marked at **every**
  occurrence. A brand named three times is flagged three times; marking only
  the first would silently hide two.
- Where two spans overlap, the higher-risk finding takes the range. Two
  findings claiming the same characters is a real outcome of deduplication
  across categories, and the reader needs one colour rather than a nested tag.
- A `raw_text` the scene does not contain yields no span, and that is not an
  error. The model paraphrased, or the scene changed between versions; the
  finding still appears in the rail with its scene and page, and only the
  inline mark is absent.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from clearcut.domain.finding import Finding, RiskLevel
from clearcut.domain.script import Scene, normalize_text

# Highest first, so a sort on this index resolves an overlap toward the
# finding a producer most needs to see.
_RISK_ORDER: tuple[RiskLevel, ...] = (
    RiskLevel.CRITICAL,
    RiskLevel.HIGH,
    RiskLevel.MEDIUM,
    RiskLevel.LOW,
)


@dataclass(frozen=True, slots=True)
class Span:
    """One finding's position in one scene's text.

    `start` and `end` index the scene's own `text` -- the string the browser
    renders -- in Unicode code points, `end` being one past the last
    character. `scene_number` is repeated on the span so it survives being
    moved out of the scene that produced it.
    """

    scene_number: int
    start: int
    end: int
    finding_id: str
    risk: RiskLevel

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError(f"start must be >= 0, got {self.start}")
        if self.end <= self.start:
            raise ValueError(f"end must be greater than start, got {self.start}..{self.end}")

    def overlaps(self, other: "Span") -> bool:
        """Whether the two spans claim any character in common."""
        return self.start < other.end and other.start < self.end


def _normalized_with_origins(text: str) -> tuple[str, list[int]]:
    """`normalize_text(text)`, plus the index in `text` each character came from.

    Rebuilt character by character rather than reusing `normalize_text`'s
    regex, because a substitution reports no offsets and the whole point here
    is carrying a match in the normalized string back to the string a reader
    sees. The output is asserted equal to `normalize_text(text)` by this
    module's tests, so the two cannot drift.
    """
    characters: list[str] = []
    origins: list[int] = []
    for index, character in enumerate(text.lower()):
        if character.isspace():
            # A whitespace run collapses to one space anchored at its first
            # character, so an offset never lands inside the run it replaced.
            if characters and characters[-1] != " ":
                characters.append(" ")
                origins.append(index)
            continue
        characters.append(character)
        origins.append(index)

    start = 1 if characters and characters[0] == " " else 0
    end = len(characters) - 1 if characters and characters[-1] == " " else len(characters)
    return "".join(characters[start:end]), origins[start:end]


def _occurrences(haystack: str, needle: str) -> list[int]:
    """Every start index at which `needle` occurs in `haystack`, left to right.

    Occurrences do not overlap each other: the search resumes past the match
    it just took, so `"aa"` in `"aaa"` is one occurrence rather than two
    sharing a character.
    """
    found: list[int] = []
    cursor = haystack.find(needle)
    while cursor != -1:
        found.append(cursor)
        cursor = haystack.find(needle, cursor + len(needle))
    return found


def _candidates(scene: Scene, findings: Iterable[Finding]) -> list[Span]:
    """One span per occurrence of every finding's `raw_text` in `scene.text`.

    Overlaps are left in: resolving them needs the whole set, so that is
    `spans_for`'s job rather than this one's.
    """
    normalized, origins = _normalized_with_origins(scene.text)
    spans: list[Span] = []
    for finding in findings:
        needle = normalize_text(finding.raw_text)
        if not needle:
            continue
        for start in _occurrences(normalized, needle):
            spans.append(
                Span(
                    scene_number=scene.number,
                    start=origins[start],
                    end=origins[start + len(needle) - 1] + 1,
                    finding_id=finding.finding_id,
                    risk=finding.risk_level,
                )
            )
    return spans


def _priority(span: Span) -> tuple[int, int, str]:
    """Risk first, then position, then id -- a total order, so two runs over
    the same findings resolve the same overlap the same way."""
    return (_RISK_ORDER.index(span.risk), span.start, span.finding_id)


def spans_for(scene: Scene, findings: Iterable[Finding]) -> tuple[Span, ...]:
    """The ordered, non-overlapping spans `findings` mark on `scene`.

    Ordered by `start`, and never overlapping. Shorter than the finding count
    when a `raw_text` does not appear in this scene, and longer when one
    appears more than once. `findings` is not filtered by `scene_number`: an
    asset deduplicated across scenes carries one finding for all of them, so
    filtering would leave every scene but the first unmarked.
    """
    accepted: list[Span] = []
    for span in sorted(_candidates(scene, findings), key=_priority):
        if any(span.overlaps(kept) for kept in accepted):
            continue
        accepted.append(span)
    return tuple(sorted(accepted, key=lambda kept: (kept.start, kept.end)))
