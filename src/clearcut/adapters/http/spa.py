"""Serves the built SPA from `web/dist` (ADR 0010: "one Cloud Run service
serves the JSON API and the static web/ build from the same container",
which is what makes same-origin serving true and removes CORS entirely).

Maps a request path to a file under `build_dir` and nothing else -- no use
case, no port, no business rule. `create_blueprint` (CP-029, `routes.py`)
owns every `/api/*` route; this module is never imported by it and never
imports it back. `create_app` (`composition.py`) mounts both blueprints on
the same app.

An `/api/*` path that matches none of `routes.py`'s literal routes must
still fail as JSON, never fall through to `index.html` -- an HTML 200 where
a JSON 404 belongs turns every frontend bug into a silent success. Flask
already tries `routes.py`'s literal routes before this blueprint's dynamic
catch-all, but the catch-all checks the `/api` prefix itself too, so that
guarantee does not rest on route-registration order alone.
"""

from pathlib import Path

from flask import Blueprint, jsonify, send_from_directory
from flask.typing import ResponseReturnValue

_API_PREFIX = "api"
_INDEX_FILE = "index.html"


def _is_api_path(request_path: str) -> bool:
    return request_path == _API_PREFIX or request_path.startswith(f"{_API_PREFIX}/")


def _missing_build_response(build_dir: Path) -> ResponseReturnValue:
    message = f"SPA build not found at {build_dir}; run `npm run build` in web/ first"
    return jsonify({"error": message}), 404


def _api_not_found_response() -> ResponseReturnValue:
    return jsonify({"error": "not found"}), 404


def create_spa_blueprint(build_dir: Path) -> Blueprint:
    """A blueprint serving `build_dir`'s static files, falling back to its
    `index.html` for any client-side route the SPA router owns -- every path
    except one starting with `/api`, which gets its own JSON 404 instead."""
    bp = Blueprint("clearcut_spa", __name__)

    def _serve(request_path: str) -> ResponseReturnValue:
        if _is_api_path(request_path):
            return _api_not_found_response()
        if not build_dir.is_dir():
            return _missing_build_response(build_dir)
        if (build_dir / request_path).is_file():
            return send_from_directory(build_dir, request_path)
        # No file at that path -- the SPA router owns it (a client-side
        # route such as `/tracker`), so it gets `index.html` at 200 rather
        # than the 404 a bare static handler would give a deep link.
        return send_from_directory(build_dir, _INDEX_FILE)

    @bp.route("/")
    def index() -> ResponseReturnValue:
        return _serve(_INDEX_FILE)

    @bp.route("/<path:request_path>")
    def static_or_fallback(request_path: str) -> ResponseReturnValue:
        return _serve(request_path)

    return bp
