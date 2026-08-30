"""Behaviour tests for infra/provision_data_plane.sh.

The script is bash, not Python, so these tests shell out to it through
``subprocess`` and assert on what it prints. ``--dry-run`` is the seam that
makes this possible without touching a real Google Cloud project: it prints
every command the script would run and executes none of them.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "infra" / "provision_data_plane.sh"


def run_script(
    args: list[str], env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_dry_run_prints_bucket_names_location_and_bq_mk() -> None:
    result = run_script(["--dry-run"])

    assert result.returncode == 0
    assert "gs://clearcut-scripts-intake" in result.stdout
    assert "gs://clearcut-legal-corpus" in result.stdout
    assert "--location=us-central1" in result.stdout
    assert "bq mk" in result.stdout
    assert "clearcut" in result.stdout


def test_dry_run_prints_a_guard_for_each_of_the_five_resources() -> None:
    result = run_script(["--dry-run"])
    out = result.stdout

    assert "gcloud storage buckets describe gs://clearcut-scripts-intake" in out
    assert "gcloud storage buckets describe gs://clearcut-legal-corpus" in out
    assert "bq show --dataset clearcut" in out
    assert "gcloud secrets list" in out
    docai_lines = [line for line in out.splitlines() if "documentai.googleapis.com" in line]
    guard_lines = [line for line in docai_lines if "-X POST" not in line]
    create_lines = [line for line in docai_lines if "-X POST" in line]
    assert guard_lines, "no Document AI guard (GET) line printed"
    assert create_lines, "no Document AI create (POST) line printed"


def test_dry_run_prints_docai_processor_id_env_line_with_placeholder() -> None:
    result = run_script(["--dry-run"])

    lines = [line for line in result.stdout.splitlines() if line.startswith("DOCAI_PROCESSOR_ID=")]
    assert len(lines) == 1
    assert lines[0] != "DOCAI_PROCESSOR_ID="


def test_missing_gcloud_exits_nonzero_before_printing_any_create() -> None:
    result = run_script(["--dry-run"], env={"PATH": ""})

    assert result.returncode != 0
    assert "gcloud" in result.stderr
    assert result.stdout == ""


def test_unknown_flag_exits_nonzero_with_usage() -> None:
    result = run_script(["--not-a-real-flag"])

    assert result.returncode != 0
    assert "Usage" in result.stderr
    assert result.stdout == ""


def test_script_has_no_syntax_errors() -> None:
    result = subprocess.run(
        ["/bin/bash", "-n", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_script_sets_strict_mode() -> None:
    source = SCRIPT.read_text()

    assert "set -euo pipefail" in source
