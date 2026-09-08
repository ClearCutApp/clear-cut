"""Scheduled scene projection batches; no web server and no user-content logs."""

import argparse
import os
import time
from datetime import UTC, datetime
from threading import Event, Thread
from uuid import uuid4

from clearcut.application.lore_projection_ports import LoreLease, LoreProjectionQueue
from clearcut.domain.durable_analysis import LeaseLost


class ProjectionHeartbeat:
    def __init__(self, queue: LoreProjectionQueue, lease: LoreLease) -> None:
        self.queue, self.lease = queue, lease
        self.stop, self.lost = Event(), Event()
        self.thread = Thread(target=self._run, daemon=True, name="lore-lease")

    def _run(self) -> None:
        while not self.stop.wait(20):
            try:
                self.queue.heartbeat(self.lease, datetime.now(UTC))
            except Exception:
                self.lost.set()
                return

    def ensure(self) -> None:
        if self.lost.is_set():
            raise LeaseLost("lore projection heartbeat lost")

    def __enter__(self) -> "ProjectionHeartbeat":
        self.thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop.set()
        self.thread.join(timeout=2)


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    from clearcut.composition import build_lore_dispatcher

    queue, projector = build_lore_dispatcher()
    owner = os.environ.get("CLOUD_RUN_EXECUTION") or uuid4().hex
    deadline = time.monotonic() + 240
    for _ in range(16):
        if time.monotonic() >= deadline:
            break
        candidates = queue.ready(datetime.now(UTC), 2)
        if not candidates:
            break
        lease = queue.claim(candidates[0], owner, datetime.now(UTC))
        if lease is None:
            continue
        with ProjectionHeartbeat(queue, lease) as heartbeat:
            projector.execute_batch(lease, heartbeat.ensure)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("scene projection failed; inspect safe outbox status") from None
