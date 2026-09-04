#!/usr/bin/env python3
"""Emit the planted screenplay SDD section 8(d) analyses, as paginated text.

Section 8(d) asserts three findings surface "with the correct page numbers",
so the page a slugline prints on is part of what is under test, not incidental
formatting. `adapters/demo/scenario.py` already declares where each scene
sits -- pages 3, 5 and 8 -- and this places them there rather than restating
the number in a second place.

The scene text comes from `scenario.py` too, so the script Document AI parses
and the scenario mock mode serves cannot drift into telling different stories.

Writes text with form feeds between pages, which `cupsfilter` turns into real
page breaks:

    .venv/bin/python infra/build_planted_script.py > script.txt
    cupsfilter script.txt > planted-script-v1.pdf
    gcloud storage cp planted-script-v1.pdf gs://clearcut-scripts-intake/demo-project/v1.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from clearcut.adapters.demo import scenario  # noqa: E402

TOTAL_PAGES = 12

TITLE = [
    "THE ROSARIO SILO",
    "",
    "An original screenplay",
    "",
    "",
    "FADE IN:",
]

# Filler exists so the planted scenes land on their declared pages. It is
# deliberately free of anything the extractor could mistake for a clearance
# event: no brands, no songs, no named real people. A finding it did not plant
# would make the "exactly 3 open items" assertion fail for a reason that has
# nothing to do with the pipeline.
FILLER = [
    "INT. EMPTY CORRIDOR - CONTINUOUS",
    "",
    "Footsteps echo. A door closes somewhere out of frame.",
    "",
    "CUT TO:",
]


def pages() -> list[str]:
    """One string per page, in order, with the planted scenes placed."""
    by_page = {scene.page_start: scene for scene in scenario.SCENES}
    out: list[str] = []
    for number in range(1, TOTAL_PAGES + 1):
        lines = list(TITLE) if number == 1 else []
        scene = by_page.get(number)
        if scene is not None:
            lines += scene.text.splitlines()
        else:
            lines += FILLER
        lines += ["", f"{number}."]
        out.append("\n".join(lines))
    return out


def main() -> int:
    sys.stdout.write("\f".join(pages()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
