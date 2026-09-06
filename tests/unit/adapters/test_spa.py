"""Unit tests for serving the built SPA from `create_app()` (CP-046, ADR
0010: "one Cloud Run service serves the JSON API and the static web/ build
from the same container", no CORS).

Every test points `create_app` at a `tmp_path` holding a stub `index.html`
and one static asset -- `npm run build` never runs here, so `web/dist` not
existing in a fresh checkout is never a test dependency.
"""

import ast
import os
from pathlib import Path

import pytest

from clearcut.composition import create_app

REPO_ROOT = Path(__file__).resolve().parents[3]
SPA_PATH = REPO_ROOT / "src" / "clearcut" / "adapters" / "http" / "spa.py"

_INDEX_MARKER = b"clearcut-spa-stub"
_ASSET_BODY = b"console.log('spa-asset-9f3a');"
_ANALYZE_BODY = {
    "project_id": "demo-project",
    "jurisdiction_code": "AR",
    "gcs_uri": "gs://clearcut-demo/planted-script-v1.pdf",
    "version": 1,
}


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "environ", {"CLEARCUT_MODE": "mock"})


@pytest.fixture
def build_dir(tmp_path: Path) -> Path:
    build = tmp_path / "dist"
    build.mkdir()
    (build / "index.html").write_text(f"<!doctype html><body>{_INDEX_MARKER.decode()}</body>")
    assets = build / "assets"
    assets.mkdir()
    (assets / "app.js").write_bytes(_ASSET_BODY)
    return build


# ---------------------------------------------------------------------------
# Criterion 1: create_app() serves the web/ build's index.html at GET /.
# ---------------------------------------------------------------------------


def test_root_serves_the_build_index_html_with_html_content_type(
    monkeypatch: pytest.MonkeyPatch, build_dir: Path
) -> None:
    _clear_env(monkeypatch)
    client = create_app(build_dir=build_dir).test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert response.content_type.startswith("text/html")
    assert _INDEX_MARKER in response.data


# ---------------------------------------------------------------------------
# Criterion 2: a client-side route deep-links to the same index.html at 200.
# ---------------------------------------------------------------------------


def test_deep_link_tracker_falls_back_to_the_spa_index(
    monkeypatch: pytest.MonkeyPatch, build_dir: Path
) -> None:
    _clear_env(monkeypatch)
    client = create_app(build_dir=build_dir).test_client()

    response = client.get("/tracker")

    assert response.status_code == 200
    assert _INDEX_MARKER in response.data


def test_deep_link_script_id_falls_back_to_the_spa_index(
    monkeypatch: pytest.MonkeyPatch, build_dir: Path
) -> None:
    _clear_env(monkeypatch)
    client = create_app(build_dir=build_dir).test_client()

    response = client.get("/script/abc")

    assert response.status_code == 200
    assert _INDEX_MARKER in response.data


# ---------------------------------------------------------------------------
# Criterion 3: an unmatched /api path never falls through to the SPA.
# ---------------------------------------------------------------------------


def test_unmatched_api_path_returns_json_404_not_the_spa_index(
    monkeypatch: pytest.MonkeyPatch, build_dir: Path
) -> None:
    _clear_env(monkeypatch)
    client = create_app(build_dir=build_dir).test_client()

    response = client.get("/api/nope")

    assert response.status_code == 404
    assert response.content_type.startswith("application/json")
    body = response.get_json()
    assert "error" in body
    assert _INDEX_MARKER not in response.data


def test_existing_api_route_is_not_shadowed_by_the_spa_catch_all(
    monkeypatch: pytest.MonkeyPatch, build_dir: Path
) -> None:
    _clear_env(monkeypatch)
    client = create_app(build_dir=build_dir).test_client()

    response = client.post("/api/projects/demo-project/scripts", json=_ANALYZE_BODY)

    # 202: the analysis is queued, not run inside the request (ADR 0013).
    assert response.status_code == 202
    assert response.content_type.startswith("application/json")


# ---------------------------------------------------------------------------
# Criterion 4: the static root is a create_app() argument, not a module-level
# constant -- two calls with two different build dirs serve two different
# builds.
# ---------------------------------------------------------------------------


def test_create_app_serves_whichever_build_dir_is_passed_in(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    first_build = tmp_path / "first"
    first_build.mkdir()
    (first_build / "index.html").write_text("<!doctype html><body>first-build</body>")
    second_build = tmp_path / "second"
    second_build.mkdir()
    (second_build / "index.html").write_text("<!doctype html><body>second-build</body>")

    _clear_env(monkeypatch)
    first_response = create_app(build_dir=first_build).test_client().get("/")
    _clear_env(monkeypatch)
    second_response = create_app(build_dir=second_build).test_client().get("/")

    assert b"first-build" in first_response.data
    assert b"second-build" in second_response.data


# ---------------------------------------------------------------------------
# Criterion 5: a missing build directory starts the service, still answers
# every /api route, and returns a 404 naming the missing build at GET /.
# ---------------------------------------------------------------------------


def test_missing_build_dir_returns_404_naming_the_missing_build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "does-not-exist"
    _clear_env(monkeypatch)
    client = create_app(build_dir=missing).test_client()

    response = client.get("/")

    assert response.status_code == 404
    body = response.get_json()
    assert str(missing) in body["error"]


def test_missing_build_dir_still_serves_every_api_route(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "does-not-exist"
    _clear_env(monkeypatch)
    client = create_app(build_dir=missing).test_client()

    response = client.post("/api/projects/demo-project/scripts", json=_ANALYZE_BODY)

    assert response.status_code == 202


# ---------------------------------------------------------------------------
# Extra coverage: a static asset under the build directory is served as-is.
# ---------------------------------------------------------------------------


def test_static_asset_is_served_from_the_build_directory(
    monkeypatch: pytest.MonkeyPatch, build_dir: Path
) -> None:
    _clear_env(monkeypatch)
    client = create_app(build_dir=build_dir).test_client()

    response = client.get("/assets/app.js")

    assert response.status_code == 200
    assert response.data == _ASSET_BODY
    assert response.content_type.startswith("text/javascript")


# ---------------------------------------------------------------------------
# Criterion 6: the SPA blueprint holds no use case, no port, no business
# rule -- it imports nothing from clearcut.application or clearcut.domain.
# ---------------------------------------------------------------------------


def test_spa_module_imports_no_use_case_port_or_domain_rule() -> None:
    tree = ast.parse(SPA_PATH.read_text())
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.append(node.module)
    disallowed = [
        name
        for name in names
        if name.startswith("clearcut.application") or name.startswith("clearcut.domain")
    ]
    assert disallowed == []
