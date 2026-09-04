"""Behaviour tests for the API documentation blueprint.

The deployed service had no way to see what it offers. A judge, or anyone
picking this up, had to read `routes.py` to learn the request shape. This
serves an OpenAPI document and a Swagger UI over it.

The sharp test is the last one: the spec must describe the routes that exist,
not the routes the SDD wishes existed. Documentation that lists three endpoints
which 404 is worse than none, because it sends a reader looking for a bug in
their own request.
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask
from flask.testing import FlaskClient

from clearcut.adapters.http.docs import create_docs_blueprint
from clearcut.adapters.http.health import create_health_blueprint
from clearcut.adapters.http.routes import create_blueprint
from clearcut.adapters.http.spa import create_spa_blueprint


def _client(*, with_spa: bool = False) -> FlaskClient:
    app = Flask(__name__)
    app.register_blueprint(create_docs_blueprint())
    if with_spa:
        app.register_blueprint(create_spa_blueprint(Path("/nonexistent-build")))
    return app.test_client()


def test_the_openapi_document_is_served_as_json() -> None:
    response = _client().get("/api/openapi.json")

    assert response.status_code == 200
    spec = response.get_json()
    assert spec["openapi"].startswith("3.")
    assert spec["info"]["title"]


def test_the_swagger_ui_is_served_as_html() -> None:
    response = _client().get("/api/docs")

    assert response.status_code == 200
    assert "text/html" in response.headers["Content-Type"]
    assert "openapi.json" in response.get_data(as_text=True)


def test_the_spa_catch_all_does_not_swallow_either() -> None:
    """Registered alongside the SPA blueprint, both still resolve.

    `create_spa_blueprint` answers every unmatched path, so registration order
    is what keeps these from becoming its JSON 404 -- the same trap
    `/api/health` has a test for.
    """
    client = _client(with_spa=True)

    assert client.get("/api/openapi.json").status_code == 200
    assert client.get("/api/docs").status_code == 200


def test_the_spec_describes_every_route_the_app_actually_serves() -> None:
    """The spec and the blueprints agree, in both directions.

    A documented path that 404s sends a reader hunting for a bug in their own
    request. An undocumented path that works is invisible. Both are caught by
    comparing the spec against Flask's own URL map rather than against a list
    someone maintains by hand.
    """
    app = Flask(__name__)
    app.register_blueprint(
        create_blueprint(_stub(), _stub(), _stub(), _stub(), _stub())  # type: ignore[arg-type]
    )
    app.register_blueprint(create_health_blueprint("live"))
    app.register_blueprint(create_docs_blueprint())

    served = {
        str(rule).replace("<item_id>", "{item_id}")
        for rule in app.url_map.iter_rules()
        if str(rule).startswith("/api/")
    }
    documented = set(_client().get("/api/openapi.json").get_json()["paths"])

    assert documented == served


class _stub:
    """Enough of a use case for `create_blueprint` to mount its routes."""

    def execute(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("the URL map is under test, not the handlers")
