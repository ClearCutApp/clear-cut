"""The live gate has to tell proof from silence (CP-055's finding).

`pytest` exits 0 when every test skips. Until 2026-09-05 `./.claude/init.sh
live` read only that exit code, so a run that contacted no service at all
printed `Result: 1 passed, 0 failed` -- the same output a fully configured
machine produces. That is how CP-055 came to be reconciled against ten live
passes that had never executed.

These tests drive the gate through a stub `pytest` on `PATH`, so they assert
the gate's decision without reaching any real service. The stub is the seam;
nothing here is monkeypatched.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
INIT_SH = ROOT / ".claude" / "init.sh"

ALL_SKIPPED = "14 skipped, 564 deselected in 1.20s"
SOME_PASSED = "8 passed, 5 skipped, 564 deselected in 61.02s"
ONE_FAILED = "1 failed, 8 passed, 5 skipped in 62.11s"


def _gate(tmp_path: Path, summary: str, exit_code: int) -> subprocess.CompletedProcess[str]:
    """Run `init.sh live` in a scratch tree whose `pytest` is a stub printing
    `summary` and exiting `exit_code`.

    `ROOT` inside the script is derived from the script's own location, so
    copying it into `tmp_path/.claude/` is what points the gate at the scratch
    tree rather than at this repository.
    """
    (tmp_path / ".claude").mkdir()
    shutil.copy(INIT_SH, tmp_path / ".claude" / "init.sh")
    (tmp_path / "tests" / "live").mkdir(parents=True)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "pytest"
    stub.write_text(f'#!/bin/sh\necho "{summary}"\nexit {exit_code}\n')
    stub.chmod(0o755)

    return subprocess.run(
        ["bash", str(tmp_path / ".claude" / "init.sh"), "live"],
        capture_output=True,
        text=True,
        env={"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path)},
    )


def test_an_all_skipped_run_is_not_reported_as_a_pass(tmp_path: Path) -> None:
    """The defect itself. Every live test skipping means no service was
    contacted; the gate must not answer that with success, because the caller
    asked whether the live tier is green and the honest answer is that it
    reached nothing."""
    result = _gate(tmp_path, ALL_SKIPPED, exit_code=0)

    assert result.returncode != 0
    assert "contacted nothing" in result.stdout
    assert "0 passed, 1 failed" in result.stdout


def test_a_run_that_reached_real_services_passes(tmp_path: Path) -> None:
    """The other half: once tests actually execute, the gate has to go green,
    or the fix above would just make the gate always fail -- which proves
    nothing either."""
    result = _gate(tmp_path, SOME_PASSED, exit_code=0)

    assert result.returncode == 0
    assert "1 passed, 0 failed" in result.stdout
    assert "contacted nothing" not in result.stdout


def test_a_failing_live_test_still_fails_the_gate(tmp_path: Path) -> None:
    """A non-zero pytest exit stays a failure and must not be re-read as a
    configuration gap: `1 failed` alongside passes is a real defect, not a
    missing credential."""
    result = _gate(tmp_path, ONE_FAILED, exit_code=1)

    assert result.returncode != 0
    assert "0 passed, 1 failed" in result.stdout
    assert "contacted nothing" not in result.stdout


def test_the_skip_reasons_survive_into_the_gate_output(tmp_path: Path) -> None:
    """`-rs` is what turns a skip into an actionable line naming the variable
    the test wanted. The gate captures pytest's output to inspect the summary,
    so it has to print what it captured -- otherwise the fix above would trade
    a false pass for an unreadable failure."""
    reasons = "SKIPPED [1] live: GRAFANA_URL, GRAFANA_TOKEN not set\n14 skipped in 1.20s"
    result = _gate(tmp_path, reasons, exit_code=0)

    assert "GRAFANA_URL, GRAFANA_TOKEN not set" in result.stdout


def test_the_live_conftest_loads_the_environment_file() -> None:
    """`requires()` reads `os.environ`, and the credentials sit in a local env
    file that nothing in the live tier used to load. The failure is silent:
    every test skips on a fully configured machine and the tier looks
    unconfigured. `main.py` already calls `load_dotenv()` for the same reason
    before `create_app()`."""
    conftest = (ROOT / "tests" / "live" / "conftest.py").read_text()

    assert "from dotenv import load_dotenv" in conftest
    assert "load_dotenv()" in conftest


@pytest.mark.parametrize("subcommand", ["check", "verify", "live"])
def test_init_sh_still_dispatches_every_subcommand(subcommand: str) -> None:
    """A shell edit that breaks the dispatcher is invisible until someone runs
    the gate it broke."""
    assert f"  {subcommand})" in INIT_SH.read_text()
