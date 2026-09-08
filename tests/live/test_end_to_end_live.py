"""Opt-in deployed acceptance. Pending and missing credentials are not proof."""

import fcntl
from pathlib import Path

import pytest
from infra.deployed_acceptance import Acceptance, HttpTransport

from tests.live.conftest import env, requires


@pytest.mark.live
@requires(
    "CLEARCUT_ACCEPTANCE_TARGET",
    "CLEARCUT_ACCEPTANCE_ID_TOKEN",
    "CLEARCUT_ACCEPTANCE_RUN_ID",
    "CLEARCUT_ACCEPTANCE_DIRECTORY",
    "CLEARCUT_ACCEPTANCE_ADVANCE",
)
def test_authenticated_deployed_synthetic_acceptance() -> None:
    assert env("CLEARCUT_ACCEPTANCE_ADVANCE") == "yes", "explicit mutation opt-in required"
    directory = Path(env("CLEARCUT_ACCEPTANCE_DIRECTORY"))
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = env("CLEARCUT_ACCEPTANCE_TARGET").rstrip("/")
    with (directory / "receipt.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = Acceptance(
            target,
            env("CLEARCUT_ACCEPTANCE_RUN_ID"),
            directory,
            HttpTransport(target, env("CLEARCUT_ACCEPTANCE_ID_TOKEN")),
        ).advance(32)
    assert result["status"] == "success", result
