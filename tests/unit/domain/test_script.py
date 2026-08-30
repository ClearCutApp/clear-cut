"""Tests for Scene, Script, and content_hash (docs/plan/sdd.md Section 2)."""

import pytest

from clearcut.domain.script import Scene, Script, content_hash


def _scene(number: int, text: str = "He runs.") -> Scene:
    return Scene(
        number=number,
        heading="EXT. BUENOS AIRES STREET - NIGHT",
        page_start=1,
        page_end=1,
        text=text,
    )


def test_hash_is_stable_across_whitespace_and_case():
    a = content_hash("EXT.  BAR\n\nHe   runs.")
    b = content_hash("ext. bar he runs.")
    assert a == b


def test_hash_strips_leading_and_trailing_whitespace():
    a = content_hash("EXT. BAR\nHe runs.\n")
    b = content_hash("EXT. BAR\nHe runs.")
    assert a == b


def test_hash_differs_for_different_text():
    a = content_hash("EXT.  BAR\n\nHe   runs.")
    b = content_hash("INT. CAR - DAY\n\nShe drives.")
    assert a != b


def test_content_hash_returns_a_sha256_hex_digest():
    digest = content_hash("some scene text")
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_scene_populates_its_own_content_hash_from_text():
    scene = _scene(1, text="EXT.  BAR\n\nHe   runs.")
    assert scene.content_hash == content_hash("EXT.  BAR\n\nHe   runs.")


def test_scene_is_frozen():
    scene = _scene(1)
    with pytest.raises(AttributeError):
        setattr(scene, "text", "changed")


def test_script_holds_its_scenes_in_order():
    scenes = [_scene(1), _scene(2), _scene(3)]
    script = Script(
        script_id="scr-1",
        project_id="proj-1",
        version=1,
        gcs_uri="gs://clearcut-scripts-intake/proj-1/v1.pdf",
        jurisdiction_code="AR",
        scenes=scenes,
    )
    assert script.scenes == scenes
    assert script.version == 1


def test_script_rejects_a_version_below_one():
    with pytest.raises(ValueError):
        Script(
            script_id="scr-1",
            project_id="proj-1",
            version=0,
            gcs_uri="gs://clearcut-scripts-intake/proj-1/v1.pdf",
            jurisdiction_code="AR",
            scenes=[],
        )


def test_script_rejects_scenes_whose_numbers_are_not_strictly_increasing():
    with pytest.raises(ValueError):
        Script(
            script_id="scr-1",
            project_id="proj-1",
            version=1,
            gcs_uri="gs://clearcut-scripts-intake/proj-1/v1.pdf",
            jurisdiction_code="AR",
            scenes=[_scene(1), _scene(1)],
        )


def test_script_rejects_scenes_out_of_order():
    with pytest.raises(ValueError):
        Script(
            script_id="scr-1",
            project_id="proj-1",
            version=1,
            gcs_uri="gs://clearcut-scripts-intake/proj-1/v1.pdf",
            jurisdiction_code="AR",
            scenes=[_scene(2), _scene(1)],
        )
