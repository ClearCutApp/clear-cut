"""Behaviour tests for infra/build_manifest.py.

The script maps GCS object URIs (one per line on stdin) onto the JSONL
metadata manifest docs/plan/infrastructure.md Section 5 describes. It makes
no network call, so these tests shell out to it through ``subprocess`` and
feed it plain strings -- no real bucket listing involved.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "infra" / "build_manifest.py"

SIX_URIS_ACROSS_THREE_JURISDICTIONS = "\n".join(
    [
        "gs://clearcut-legal-corpus/argentina/ley-11723.pdf",
        "gs://clearcut-legal-corpus/argentina/ley-25446.pdf",
        "gs://clearcut-legal-corpus/usa/title-17.pdf",
        "gs://clearcut-legal-corpus/usa/dmca.pdf",
        "gs://clearcut-legal-corpus/mexico/ley-federal-derecho-autor.pdf",
        "gs://clearcut-legal-corpus/mexico/ley-propiedad-industrial.pdf",
    ]
)


def run_script(stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT)],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def test_pipes_six_uris_across_three_jurisdictions_and_emits_six_lines() -> None:
    result = run_script(SIX_URIS_ACROSS_THREE_JURISDICTIONS)

    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 6

    parsed = [json.loads(line) for line in lines]
    jurisdictions = [entry["structData"]["jurisdiction"] for entry in parsed]
    assert jurisdictions == [
        "argentina",
        "argentina",
        "usa",
        "usa",
        "mexico",
        "mexico",
    ]


def test_manifest_line_has_id_structdata_and_content_shape() -> None:
    result = run_script("gs://clearcut-legal-corpus/argentina/ley-11723.pdf\n")

    entry = json.loads(result.stdout.splitlines()[0])
    assert entry["id"]
    assert entry["structData"]["jurisdiction"] == "argentina"
    assert entry["content"]["mimeType"] == "application/pdf"
    assert entry["content"]["uri"] == "gs://clearcut-legal-corpus/argentina/ley-11723.pdf"


def test_uri_under_unmatched_prefix_exits_nonzero_naming_the_uri() -> None:
    bad_uri = "gs://clearcut-legal-corpus/atlantis/some-law.pdf"

    result = run_script(bad_uri + "\n")

    assert result.returncode != 0
    assert bad_uri in result.stderr
    assert result.stdout == ""
