"""Scheduled bounded analytics delivery; run separately from the web server."""

import os
from uuid import uuid4

from clearcut.composition import build_activity_dispatcher


def main() -> None:
    dispatcher = build_activity_dispatcher()
    dispatcher.dispatch(os.environ.get("CLOUD_RUN_EXECUTION") or uuid4().hex)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never export provider exception chains or credentials to Job logs.
        raise SystemExit("activity delivery failed; inspect safe outbox status") from None
