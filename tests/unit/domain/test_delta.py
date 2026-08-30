"""Tests for diff_scenes and SceneDelta (docs/plan/sdd.md Section 4.3, ADR 0007)."""

import pytest

from clearcut.domain.delta import DeltaKind, SceneDelta, diff_scenes
from clearcut.domain.script import Scene

_HEADING = "EXT. BUENOS AIRES STREET - NIGHT"


def _scene(number: int, heading: str = _HEADING, text: str = "He runs.") -> Scene:
    return Scene(number=number, heading=heading, page_start=1, page_end=1, text=text)


def test_unchanged_scene_present_in_both_versions_with_equal_hash():
    old = [_scene(1)]
    new = [_scene(1)]

    deltas = diff_scenes(old, new)

    assert deltas == [
        SceneDelta(
            scene_number=1,
            heading=_HEADING,
            kind=DeltaKind.UNCHANGED,
            old_hash=old[0].content_hash,
            new_hash=new[0].content_hash,
        )
    ]


def test_same_key_different_hash_is_changed_with_both_hashes():
    old = [_scene(1, text="He runs.")]
    new = [_scene(1, text="He walks.")]

    deltas = diff_scenes(old, new)

    assert deltas == [
        SceneDelta(
            scene_number=1,
            heading=_HEADING,
            kind=DeltaKind.CHANGED,
            old_hash=old[0].content_hash,
            new_hash=new[0].content_hash,
        )
    ]


def test_scene_present_only_in_new_is_added_with_no_old_hash():
    new = [_scene(1)]

    deltas = diff_scenes([], new)

    assert deltas == [
        SceneDelta(
            scene_number=1,
            heading=_HEADING,
            kind=DeltaKind.ADDED,
            old_hash=None,
            new_hash=new[0].content_hash,
        )
    ]


def test_scene_present_only_in_old_is_removed_with_no_new_hash():
    old = [_scene(1)]

    deltas = diff_scenes(old, [])

    assert deltas == [
        SceneDelta(
            scene_number=1,
            heading=_HEADING,
            kind=DeltaKind.REMOVED,
            old_hash=old[0].content_hash,
            new_hash=None,
        )
    ]


def test_matching_number_with_changed_heading_is_removed_plus_added_not_changed():
    old = [_scene(1, heading="EXT. BAR - NIGHT")]
    new = [_scene(1, heading="EXT. BAR - DAY")]

    deltas = diff_scenes(old, new)

    assert len(deltas) == 2
    assert {delta.kind for delta in deltas} == {DeltaKind.REMOVED, DeltaKind.ADDED}


def test_every_input_scene_appears_exactly_once_per_version_it_belongs_to():
    old = [_scene(1), _scene(2), _scene(3)]
    new = [_scene(1), _scene(2, text="changed"), _scene(4)]

    deltas = diff_scenes(old, new)

    carrying_old_hash = [delta for delta in deltas if delta.old_hash is not None]
    carrying_new_hash = [delta for delta in deltas if delta.new_hash is not None]
    assert len(carrying_old_hash) == len(old)
    assert len(carrying_new_hash) == len(new)


def test_duplicate_key_within_one_version_raises_value_error_naming_the_key():
    old = [_scene(1), _scene(1)]

    with pytest.raises(ValueError, match=r"1.*EXT\. BUENOS AIRES STREET - NIGHT"):
        diff_scenes(old, [])


def test_empty_old_returns_every_new_scene_as_added():
    new = [_scene(1), _scene(2)]

    deltas = diff_scenes([], new)

    assert len(deltas) == 2
    assert all(delta.kind == DeltaKind.ADDED for delta in deltas)


def test_reordering_scenes_in_the_input_lists_does_not_change_the_result():
    """Joining is by (number, heading) key, not by list position — a scene
    read in a different order between versions still comes back UNCHANGED.

    scene_a and scene_b carry different text so their content_hash values
    differ. A positional-zip join would pair old[0] with new[0] (b-with-a)
    and old[1] with new[1] (a-with-b), see mismatched hashes, and report
    CHANGED for both — only a key join pairs each scene with itself across
    the swapped order and reports UNCHANGED.
    """
    scene_a = _scene(1, heading="EXT. BAR - NIGHT", text="He runs.")
    scene_b = _scene(2, heading="INT. CAR - DAY", text="She waits.")
    old = [scene_a, scene_b]
    new = [scene_b, scene_a]

    deltas = diff_scenes(old, new)

    assert len(deltas) == 2
    assert all(delta.kind == DeltaKind.UNCHANGED for delta in deltas)
