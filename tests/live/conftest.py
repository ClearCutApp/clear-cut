"""Shared machinery for the live tier (AGENT.md section 5).

Every test here builds the same adapter the unit tests build, with the real SDK
client passed in where the unit test passes a hand-written fake. Nothing is
monkeypatched, because nothing needs to be: section 5 already forbids
`unittest.mock`, so every seam in this codebase is a constructor argument.

A live test has two honest outcomes. It passes with credentials present, or it
skips because they are absent. It must never pass without them -- that would
mean it reached nothing, which is the failure the tier exists to catch.
"""

import os
import uuid

import pytest

# Re-exported so the live tier can read back the spans and metrics a real call
# recorded. Fixtures are directory-scoped, so importing the name here is what
# makes `isolated_otel` resolvable from `tests/live/`.
from tests.unit.conftest import isolated_otel  # noqa: F401


def requires(*names: str) -> pytest.MarkDecorator:
    """Skip unless every named variable is set to a non-blank value.

    The reason names the missing variables, so `pytest -rs` tells you what to
    configure rather than only that something was absent.
    """
    missing = [name for name in names if not os.environ.get(name, "").strip()]
    return pytest.mark.skipif(
        bool(missing),
        reason=f"live: {', '.join(missing)} not set",
    )


def env(name: str) -> str:
    """Read a variable a `requires` marker has already proven present.

    Raises rather than returning a default: reaching here with the variable
    unset means the marker and the body disagree about what the test needs.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is unset; this test's `requires` marker is out of sync")
    return value


def scratch_id(prefix: str) -> str:
    """A project id unique to one run.

    Live tests write to shared services. Without this, two runs collide and a
    stale row from the previous one can satisfy an assertion the current run
    should have failed.
    """
    return f"{prefix}-{uuid.uuid4().hex[:12]}"
