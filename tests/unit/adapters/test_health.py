"""Behaviour tests for the health blueprint.

`CLEARCUT_MODE` decided whether every number on the screen came from a real
service or from `adapters/demo/scenario.py`, and nothing told the browser
which. The SPA rendered planted findings with exactly the confidence it renders
real ones. This endpoint is what lets the page say so.

It is its own blueprint rather than a sixth route on `create_blueprint`, for
the same reason the SPA is: it maps to no use case, so putting it there would
mean handing a route module something that is not a use case to call.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from clearcut.adapters.http.health import create_health_blueprint
from clearcut.adapters.http.spa import create_spa_blueprint


def _client(mode: str, *, with_spa: bool = False) -> FlaskClient:
    app = Flask(__name__)
    app.register_blueprint(create_health_blueprint(mode))
    if with_spa:
        app.register_blueprint(create_spa_blueprint(Path("/nonexistent-build")))
    return app.test_client()


@pytest.mark.parametrize("mode", ["mock", "live"])
def test_reports_the_mode_it_was_built_with(mode: str) -> None:
    response = _client(mode).get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {"mode": mode}


def test_mock_and_live_are_distinguishable_from_the_response_alone() -> None:
    """The whole point: a client can tell planted data from real data.

    Asserted as a pair rather than twice over, because a handler returning one
    constant would satisfy either test on its own.
    """
    mock_body = _client("mock").get("/api/health").get_json()
    live_body = _client("live").get("/api/health").get_json()

    assert mock_body != live_body
    assert mock_body["mode"] == "mock"
    assert live_body["mode"] == "live"


def test_the_spa_catch_all_does_not_swallow_it() -> None:
    """Registered alongside the SPA blueprint, `/api/health` still resolves.

    `create_spa_blueprint` answers every unmatched path, returning a JSON 404
    for anything under `/api`. Registration order is what keeps health from
    becoming that 404, and `create_app` registers both -- so without this test
    the endpoint could work in isolation and 404 in the real application.
    """
    response = _client("mock", with_spa=True).get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {"mode": "mock"}
