"""The endpoint that tells a browser whether anything it sees is real.

`CLEARCUT_MODE=mock` serves the planted scenario in `adapters/demo/scenario.py`
(D36), and until this existed the SPA had no way to know. It rendered constants
with exactly the confidence it renders a real Gemini extraction, which is what
makes a mocked demo read as a dishonest one rather than a hedged one.

Its own blueprint rather than a sixth route on `create_blueprint`, for the same
reason `spa.py` is: health maps to no use case, and `create_blueprint` takes use
cases. The mode arrives as an argument because no adapter module may read the
environment -- `composition.py` owns every such read (AGENT.md section 2), and
`test_composition.py` enforces it.
"""

from __future__ import annotations

from flask import Blueprint, jsonify
from flask.typing import ResponseReturnValue


def create_health_blueprint(mode: str) -> Blueprint:
    """A blueprint serving `GET /api/health` with the mode it was built with.

    Register it before the SPA blueprint. That one answers every unmatched
    path, so a later registration would turn this route into the SPA's JSON
    404 for `/api` paths.
    """
    bp = Blueprint("clearcut_health", __name__)

    @bp.route("/api/health")
    def health() -> ResponseReturnValue:
        return jsonify({"mode": mode})

    return bp
