"""ClearCut's fresh-clone entrypoint (CP-052). `load_dotenv()` runs before
anything else so a local `.env` is in place before `create_app()` reads
`CLEARCUT_MODE`; `app` is bound at module level so `main:app` resolves for a
WSGI server or the GCP Python buildpack. Serving only happens under
`__main__` -- `import main` must never open a socket.
"""

import os

from dotenv import load_dotenv

from clearcut.composition import create_app

load_dotenv()

app = create_app()


def _port() -> int:
    """The bind port, read at call time rather than inlined, so a test can
    observe it without starting a server."""
    return int(os.environ.get("PORT", "8080"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=_port())
