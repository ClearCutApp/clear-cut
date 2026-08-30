"""Tests for the NER-label-to-category mapping (CP-003).

SDD reference: plan/sdd.md Section 2.
"""

import pytest

from clearcut.domain.finding import Category, NerLabel
from clearcut.domain.taxonomy import category_for


@pytest.mark.parametrize(
    "label,expected",
    [
        (NerLabel.BRAND, Category.INDUSTRIAL_PROPERTY),
        (NerLabel.MUSIC_EXISTING, Category.COPYRIGHT_WORKS),
        (NerLabel.MUSIC_ORIGINAL, Category.COPYRIGHT_WORKS),
        (NerLabel.ART_LIT, Category.COPYRIGHT_WORKS),
        (NerLabel.MEDIA_AV, Category.COPYRIGHT_WORKS),
        (NerLabel.TALENT_CHARACTER, Category.PERSONALITY_IMAGE),
        (NerLabel.REAL_PERSON, Category.PERSONALITY_IMAGE),
        (NerLabel.PROPS_DESIGN, Category.INTEGRATED_VISUAL),
        (NerLabel.LOCATION_PRIV, Category.LOCATIONS_PERMITS),
        (NerLabel.LOCATION_PUB, Category.LOCATIONS_PERMITS),
        (NerLabel.SPECIAL_SYMBOL, Category.SPECIAL_SYMBOLS),
    ],
)
def test_category_for_maps_every_ner_label_per_sdd(label, expected):
    assert category_for(label) == expected


def test_music_and_art_labels_all_map_to_copyright_works():
    labels = {
        NerLabel.MUSIC_EXISTING,
        NerLabel.MUSIC_ORIGINAL,
        NerLabel.ART_LIT,
        NerLabel.MEDIA_AV,
    }
    assert {category_for(label) for label in labels} == {Category.COPYRIGHT_WORKS}


def test_category_for_rejects_a_value_that_is_not_a_ner_label():
    with pytest.raises(ValueError, match="not-a-real-label"):
        category_for("not-a-real-label")
