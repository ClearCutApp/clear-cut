"""Scheduled Cloud Run Job: reconcile persisted launches without HTTP threads."""

import os
from datetime import UTC, datetime
from uuid import uuid4

from clearcut.composition import build_analysis_dispatcher
from clearcut.domain.errors import SourceUnavailable


def main() -> None:
    jobs, launcher = build_analysis_dispatcher()
    owner = os.environ.get("CLOUD_RUN_EXECUTION") or uuid4().hex
    at = datetime.now(UTC)
    for analysis_id in jobs.ready(at):
        if not jobs.reserve_launch(analysis_id, owner, at):
            continue
        try:
            operation = launcher.launch(analysis_id)
            jobs.acknowledge_launch(analysis_id, owner, operation)
        except SourceUnavailable:
            # A lost launch response can mean an accepted execution. The next
            # scheduled pass may safely relaunch after reservation expiry;
            # worker fencing, not transport exactly-once, prevents publication.
            continue


if __name__ == "__main__":
    main()
