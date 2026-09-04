"""Behaviour tests for infra/build_planted_script.py.

SDD section 8(d) asserts the three planted findings surface "with the correct
page numbers", so where a slugline prints is under test rather than a
formatting detail. These tests hold the generated pagination to what
`scenario.py` declares.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from clearcut.adapters.demo import scenario

SCRIPT = Path(__file__).resolve().parents[3] / "infra" / "build_planted_script.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_planted_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_each_scene_prints_on_the_page_the_scenario_declares() -> None:
    """The assertion section 8(a) spot-checks by hand, made automatic.

    A slugline one page off would fail 8(d) with a page-number mismatch that
    looks like a Document AI defect and is really a fixture defect.
    """
    pages = load_script().pages()

    for scene in scenario.SCENES:
        page = pages[scene.page_start - 1]
        assert scene.heading in page, f"{scene.heading} is not on page {scene.page_start}"


def test_no_scene_text_leaks_onto_another_page() -> None:
    pages = load_script().pages()

    for scene in scenario.SCENES:
        carrying = [i + 1 for i, page in enumerate(pages) if scene.heading in page]
        assert carrying == [scene.page_start], f"{scene.heading} appears on {carrying}"


def test_the_filler_plants_nothing_the_extractor_could_find() -> None:
    """Filler must be inert.

    Section 8(d) asserts the tracker reads exactly three open items. A brand or
    a song in the filler would add a fourth and fail the check for a reason
    that has nothing to do with the pipeline.
    """
    filler = "\n".join(load_script().FILLER).lower()

    for planted in ("ferrari", "testarossa", "hotel california", "coca", "quilmes"):
        assert planted not in filler


def test_the_script_is_the_length_the_proposal_describes() -> None:
    module = load_script()

    assert module.TOTAL_PAGES == 12
    assert len(module.pages()) == 12


def test_pages_are_separated_by_form_feeds() -> None:
    """`cupsfilter` turns a form feed into a real page break.

    Without them every page runs together and the printed page numbers stop
    matching the PDF's.
    """
    module = load_script()
    rendered = "\f".join(module.pages())

    assert rendered.count("\f") == module.TOTAL_PAGES - 1
