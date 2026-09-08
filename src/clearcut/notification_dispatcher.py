"""Scheduled bounded private notification delivery, separate from Flask."""

import argparse
import os
import uuid

from clearcut.composition import build_notification_dispatcher


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    build_notification_dispatcher().dispatch(
        os.environ.get("CLOUD_RUN_EXECUTION") or uuid.uuid4().hex
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("notification delivery failed; inspect safe outbox status") from None
