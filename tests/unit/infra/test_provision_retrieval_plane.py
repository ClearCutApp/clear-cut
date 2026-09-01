"""Behaviour tests for infra/provision_retrieval_plane.sh.

The script is bash, not Python, so these tests shell out to it through
``subprocess`` and assert on what it prints. ``--dry-run`` is the seam that
makes this possible without touching a real Google Cloud project: it prints
every command the script would run and executes none of them.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "infra" / "provision_retrieval_plane.sh"

INDEXABLE_WARNING_MARKER = "Indexable"
WARNING_CLOSING_LINE = "=" * 70


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


@pytest.fixture
def manifest_file(tmp_path: Path) -> Path:
    manifest = tmp_path / "legal_corpus_manifest.jsonl"
    manifest.write_text(
        '{"id": "argentina-ley-11723", "structData": {"jurisdiction": "argentina"}, '
        '"content": {"mimeType": "application/pdf", '
        '"uri": "gs://clearcut-legal-corpus/argentina/ley-11723.pdf"}}\n'
    )
    return manifest


def env_with_manifest(manifest: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["MANIFEST_FILE"] = str(manifest)
    return env


def test_dry_run_enables_discoveryengine_api(manifest_file: Path) -> None:
    result = run_script(["--dry-run"], env=env_with_manifest(manifest_file))

    assert result.returncode == 0, result.stderr
    assert "discoveryengine.googleapis.com" in result.stdout


def test_dry_run_creates_data_store_over_corpus_bucket(manifest_file: Path) -> None:
    result = run_script(["--dry-run"], env=env_with_manifest(manifest_file))

    assert "gs://clearcut-legal-corpus" in result.stdout
    assert "dataStores" in result.stdout


def test_dry_run_imports_the_manifest_file(manifest_file: Path) -> None:
    result = run_script(["--dry-run"], env=env_with_manifest(manifest_file))

    assert str(manifest_file) in result.stdout
    assert "documents:import" in result.stdout


def test_dry_run_registers_the_agent_builder_app(manifest_file: Path) -> None:
    """`create_engine`/`create_engine_call` still provision the Agent
    Builder agent app: CP-051 (Decision D40) struck the unread
    `AGENT_BUILDER_AGENT_ID` documentation claim, not this API call --
    section 5 of infrastructure.md still asks for the app to exist as a
    grounding source attachment, out of scope for this checkpoint to judge."""
    result = run_script(["--dry-run"], env=env_with_manifest(manifest_file))

    assert "collections/default_collection/engines" in result.stdout
    assert "engineId=clearcut-project-qa" in result.stdout


def test_dry_run_prints_vertex_search_data_store_id_env_line(manifest_file: Path) -> None:
    result = run_script(["--dry-run"], env=env_with_manifest(manifest_file))

    prefix = "VERTEX_SEARCH_DATA_STORE_ID="
    lines = [line for line in result.stdout.splitlines() if line.startswith(prefix)]
    assert len(lines) == 1
    assert lines[0] == "VERTEX_SEARCH_DATA_STORE_ID=clearcut-legal-corpus"


def test_missing_gcloud_exits_nonzero_before_printing_any_create(manifest_file: Path) -> None:
    env = env_with_manifest(manifest_file)
    env["PATH"] = ""

    result = run_script(["--dry-run"], env=env)

    assert result.returncode != 0
    assert "gcloud" in result.stderr
    assert result.stdout == ""


def test_unknown_flag_exits_nonzero_with_usage(manifest_file: Path) -> None:
    result = run_script(["--not-a-real-flag"], env=env_with_manifest(manifest_file))

    assert result.returncode != 0
    assert "Usage" in result.stderr
    assert result.stdout == ""


def test_missing_manifest_exits_nonzero_before_creating_data_store(tmp_path: Path) -> None:
    env = env_with_manifest(tmp_path / "does-not-exist.jsonl")

    result = run_script(["--dry-run"], env=env)

    assert result.returncode != 0
    assert "manifest" in result.stderr
    assert result.stdout == ""


def test_empty_manifest_exits_nonzero_before_creating_data_store(tmp_path: Path) -> None:
    empty_manifest = tmp_path / "empty.jsonl"
    empty_manifest.write_text("")

    result = run_script(["--dry-run"], env=env_with_manifest(empty_manifest))

    assert result.returncode != 0
    assert "manifest" in result.stderr
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


def test_dry_run_prints_indexable_warning_as_the_last_block(manifest_file: Path) -> None:
    result = run_script(["--dry-run"], env=env_with_manifest(manifest_file))
    out = result.stdout

    # The warning must be the terminal text of stdout, not merely the last
    # blank-line-delimited block -- trailing output with no preceding blank
    # line would otherwise join the warning's block undetected. Asserting
    # that stdout, once trailing whitespace is stripped, ends with the
    # warning's own closing line catches that case: anything printed after
    # the warning, blank-line-separated or not, moves this line off the end.
    assert out.rstrip().endswith(WARNING_CLOSING_LINE), out

    blocks = [block for block in out.split("\n\n") if block.strip()]
    assert blocks, "script printed nothing"
    last_block = blocks[-1]

    assert INDEXABLE_WARNING_MARKER in last_block
    assert "jurisdiction" in last_block
    assert "console" in last_block.lower()
