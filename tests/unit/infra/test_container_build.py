"""Static checks on the container definition (ADR 0010).

These do not build the image. They hold the Dockerfile and the ignore files to
the handful of properties that are silent when wrong, which is the class of
defect this repo keeps producing: a container that starts, answers nothing, and
looks healthy.

Building the image is the real proof and is not something a unit test can do.
`./.claude/init.sh live` is where a running container would be asserted against;
until someone builds and deploys it, this file is the only thing standing
between a typo and a broken demo.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DOCKERFILE = ROOT / "Dockerfile"
DOCKERIGNORE = ROOT / ".dockerignore"
GCLOUDIGNORE = ROOT / ".gcloudignore"


def test_a_dockerfile_exists() -> None:
    """ADR 0010 bakes the Vite build into one image.

    Without this file `gcloud run deploy --source .` falls back to buildpacks,
    which need a requirements.txt this project does not have, and which would
    ship no `web/dist` because .gitignore excludes it.
    """
    assert DOCKERFILE.is_file()


@pytest.mark.parametrize("ignore_file", [DOCKERIGNORE, GCLOUDIGNORE])
def test_secrets_never_enter_the_build_context(ignore_file: Path) -> None:
    """`.env` holds ten live credentials. It must not reach the image.

    A COPY of the repository root picks it up by default, and the resulting
    layer is readable by anyone who can pull the image.
    """
    assert ignore_file.is_file(), f"{ignore_file.name} is missing"
    patterns = {
        line.strip()
        for line in ignore_file.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    assert ".env" in patterns, f"{ignore_file.name} does not exclude .env"


def test_the_server_binds_every_interface_on_the_injected_port() -> None:
    """Cloud Run routes to `$PORT` on `0.0.0.0`.

    `main.py`'s `__main__` block binds 127.0.0.1, which is right for local use
    and unreachable inside a container: the revision would go healthy-looking
    and answer nothing.
    """
    content = DOCKERFILE.read_text()

    assert "0.0.0.0" in content, "the container must bind 0.0.0.0, not localhost"
    assert "$PORT" in content or "${PORT}" in content, (
        "the bind port must come from Cloud Run's PORT variable"
    )


def test_the_frontend_is_built_inside_the_image() -> None:
    """The SPA blueprint serves `web/dist`, which .gitignore excludes.

    So the build has to happen in the image. If it does not, Flask serves a
    directory that is not there and every page is the missing-build response.
    """
    content = DOCKERFILE.read_text()

    assert "npm" in content, "no npm step: the Vite build never runs"
    assert "web/dist" in content, "the built SPA is never copied into the runtime stage"


def test_the_runtime_stage_carries_no_build_toolchain() -> None:
    """Multi-stage, so node and the dev dependencies stay out of the runtime.

    Asserted through the stage count rather than by naming an image: a single
    FROM means npm and its node_modules ship to production.
    """
    froms = [
        line for line in DOCKERFILE.read_text().splitlines() if line.strip().startswith("FROM ")
    ]

    assert len(froms) >= 2, f"expected a multi-stage build, found {len(froms)} FROM line(s)"


def test_the_server_the_cmd_invokes_is_a_declared_dependency() -> None:
    """The WSGI server is named only in the Dockerfile, so nothing else checks it.

    `test_declared_dependencies.py` walks imports under `src/clearcut/`, and
    gunicorn is never imported -- it is a command. That leaves a dependency
    whose absence surfaces only as a container that exits immediately on its
    first and only start, which is the worst place to find out.
    """
    cmd = next(line for line in DOCKERFILE.read_text().splitlines() if line.startswith("CMD "))
    server = next(
        candidate for candidate in ("gunicorn", "uvicorn", "waitress") if candidate in cmd
    )

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    declared = " ".join(pyproject["project"]["dependencies"])

    assert server in declared, (
        f"the Dockerfile's CMD runs {server}, which [project] dependencies does "
        "not declare, so `pip install .` inside the image will not provide it"
    )
