"""Tests for `main.py`, the fresh-clone entrypoint `./.claude/init.sh` and
the README's `CLEARCUT_MODE=mock python main.py` command exist to make true
(CP-052).

`main.py` builds `app = create_app()` at module import time, so every test
here clears the environment first and evicts any cached `main` module before
re-importing -- a cached import from an earlier test would silently reuse
whatever environment built it, hiding exactly the socket-on-import
regression criterion (a) exists to catch.
"""

import importlib
import sys
from types import ModuleType

import pytest
from flask import Flask

from tests.unit.test_composition import _clear_env, _forbid_sockets

_ANALYZE_BODY = {
    "project_id": "demo-project",
    "jurisdiction_code": "AR",
    "gcs_uri": "gs://clearcut-demo/planted-script-v1.pdf",
    "version": 1,
}

# One route per domain the partition serves (ADR 0012), which is what this
# test is for: proving `main.app` mounted the real blueprints rather than an
# empty app. The full twenty-operation surface is held against
# `docs/api/openapi.yaml` by the drift test, not restated here.
_DEMO_ROUTES = (
    "/api/health",
    "/api/projects",
    "/api/projects/<project_id>/scripts",
    "/api/projects/<project_id>/analyses/<analysis_id>",
    "/api/projects/<project_id>/tracker-items/<item_id>",
    "/api/projects/<project_id>/bible",
    "/api/projects/<project_id>/questions",
)


def _import_main(monkeypatch: pytest.MonkeyPatch, **env: str) -> ModuleType:
    """Clears the environment to exactly `env`, evicts any cached `main`
    module, and imports it fresh."""
    _clear_env(monkeypatch, **env)
    sys.modules.pop("main", None)
    return importlib.import_module("main")


# ---------------------------------------------------------------------------
# Criterion (a): under a cleared env with CLEARCUT_MODE=mock, `import main`
# succeeds, `main.app` is a Flask application, and no socket is opened.
# ---------------------------------------------------------------------------


def test_import_builds_a_flask_app_with_no_socket_opened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _forbid_sockets(monkeypatch)
    main = _import_main(monkeypatch, CLEARCUT_MODE="mock")
    assert isinstance(main.app, Flask)


# ---------------------------------------------------------------------------
# Criterion (b): main.app.url_map carries all five demo routes.
# ---------------------------------------------------------------------------


def test_app_url_map_carries_a_route_from_every_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main = _import_main(monkeypatch, CLEARCUT_MODE="mock")
    rules = {rule.rule for rule in main.app.url_map.iter_rules()}
    for path in _DEMO_ROUTES:
        assert path in rules


# ---------------------------------------------------------------------------
# Criterion (c): one request driven through main.app.test_client() exercises
# the real wiring, not a stub.
# ---------------------------------------------------------------------------


def test_a_request_through_the_test_client_queues_an_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """202 rather than 200 since ADR 0013: the upload queues a job and answers
    with where to read it, because the pipeline it starts takes twelve to
    twenty minutes against real services and no browser holds a request that
    long. The `Location` is the assertion that matters -- a 202 with nowhere to
    poll would be a worse contract than the blocking call it replaced."""
    main = _import_main(monkeypatch, CLEARCUT_MODE="mock")
    response = main.app.test_client().post("/api/projects/demo-project/scripts", json=_ANALYZE_BODY)
    assert response.status_code == 202
    assert response.headers["Location"].startswith("/api/projects/demo-project/analyses/")


# ---------------------------------------------------------------------------
# _port(): readable without starting a server, defaults to 8080, honours
# PORT.
# ---------------------------------------------------------------------------


def test_port_defaults_to_8080(monkeypatch: pytest.MonkeyPatch) -> None:
    main = _import_main(monkeypatch, CLEARCUT_MODE="mock")
    assert main._port() == 8080


def test_port_honours_the_port_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    main = _import_main(monkeypatch, CLEARCUT_MODE="mock", PORT="5000")
    assert main._port() == 5000


# ---------------------------------------------------------------------------
# Failure path: importing main must never start a server. Deleting the
# `if __name__ == "__main__":` guard turns this red.
# ---------------------------------------------------------------------------


def test_importing_main_never_starts_a_server(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("Flask.run was called while importing main")

    monkeypatch.setattr(Flask, "run", _raise_if_called)
    _import_main(monkeypatch, CLEARCUT_MODE="mock")
