"""The NER-label-to-category mapping (SDD Section 2).

This module is the one place that owns the eleven-tag-to-eight-category
mapping, so a model's own category string is never trusted directly.
"""

from clearcut.domain.finding import Category, NerLabel

_CATEGORY_FOR_LABEL: dict[NerLabel, Category] = {
    NerLabel.BRAND: Category.INDUSTRIAL_PROPERTY,
    NerLabel.MUSIC_EXISTING: Category.COPYRIGHT_WORKS,
    NerLabel.MUSIC_ORIGINAL: Category.COPYRIGHT_WORKS,
    NerLabel.ART_LIT: Category.COPYRIGHT_WORKS,
    NerLabel.MEDIA_AV: Category.COPYRIGHT_WORKS,
    NerLabel.TALENT_CHARACTER: Category.PERSONALITY_IMAGE,
    NerLabel.REAL_PERSON: Category.PERSONALITY_IMAGE,
    NerLabel.PROPS_DESIGN: Category.INTEGRATED_VISUAL,
    NerLabel.LOCATION_PRIV: Category.LOCATIONS_PERMITS,
    NerLabel.LOCATION_PUB: Category.LOCATIONS_PERMITS,
    NerLabel.SPECIAL_SYMBOL: Category.SPECIAL_SYMBOLS,
}


def category_for(label: NerLabel) -> Category:
    """The Category an NerLabel maps to.

    Raises ValueError naming the offending value when `label` is not a
    NerLabel, so an unrecognized model output cannot become an untyped
    category.
    """
    if not isinstance(label, NerLabel):
        raise ValueError(f"not a NerLabel: {label!r}")
    return _CATEGORY_FOR_LABEL[label]
