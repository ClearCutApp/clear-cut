"""The Finding aggregate and its supporting enums (SDD Section 2).

One detected clearance event: a script fragment mapped to an IP category, an
optional NER label, a risk level, and the citations backing it.
"""

import enum
from dataclasses import dataclass, field


class RiskLevel(enum.StrEnum):
    """How urgently a finding needs clearance action."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    def raised(self) -> "RiskLevel":
        """The next level up, or CRITICAL itself once already there."""
        order = (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL)
        next_index = min(order.index(self) + 1, len(order) - 1)
        return order[next_index]


class Category(enum.StrEnum):
    """The eight IP categories a Finding falls under (SDD Section 2)."""

    INDUSTRIAL_PROPERTY = "INDUSTRIAL_PROPERTY"
    COPYRIGHT_WORKS = "COPYRIGHT_WORKS"
    PERSONALITY_IMAGE = "PERSONALITY_IMAGE"
    INTEGRATED_VISUAL = "INTEGRATED_VISUAL"
    LOCATIONS_PERMITS = "LOCATIONS_PERMITS"
    SPECIAL_SYMBOLS = "SPECIAL_SYMBOLS"
    CONTINUITY = "CONTINUITY"
    POLICY = "POLICY"


class NerLabel(enum.StrEnum):
    """The eleven NER tags the extractor emits (SDD Section 2)."""

    BRAND = "BRAND"
    MUSIC_EXISTING = "MUSIC_EXISTING"
    MUSIC_ORIGINAL = "MUSIC_ORIGINAL"
    ART_LIT = "ART_LIT"
    MEDIA_AV = "MEDIA_AV"
    TALENT_CHARACTER = "TALENT_CHARACTER"
    REAL_PERSON = "REAL_PERSON"
    PROPS_DESIGN = "PROPS_DESIGN"
    LOCATION_PRIV = "LOCATION_PRIV"
    LOCATION_PUB = "LOCATION_PUB"
    SPECIAL_SYMBOL = "SPECIAL_SYMBOL"


# Categories the Project Bible audit produces; they carry no NER label
# because nothing in the script text was extracted for them (SDD Section 2).
_LABELLESS_CATEGORIES = frozenset({Category.CONTINUITY, Category.POLICY})


@dataclass(frozen=True)
class Citation:
    """One source backing a finding or a grounded answer."""

    uri: str
    title: str
    snippet: str


@dataclass(frozen=True)
class Finding:
    """One detected clearance event (SDD Section 2)."""

    finding_id: str
    scene_number: int
    page: int
    raw_text: str
    category: Category
    ner_label: NerLabel | None
    risk_level: RiskLevel
    required_document: str
    citations: tuple[Citation, ...] = field(default_factory=tuple)
    contradicts: str | None = None

    def __post_init__(self) -> None:
        if self.category in _LABELLESS_CATEGORIES and self.ner_label is not None:
            raise ValueError(f"{self.category} findings carry no ner_label, got {self.ner_label!r}")
