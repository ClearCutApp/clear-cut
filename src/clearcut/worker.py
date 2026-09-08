"""Cloud Run Job entrypoint: python -m clearcut.worker --analysis-id <id>."""

import argparse
import json
import os
from datetime import UTC, datetime
from threading import Event, Thread
from uuid import uuid4

from clearcut.application.durable_ports import DurableJobs
from clearcut.domain.durable_analysis import AnalysisCancelled, DurableJob, LeaseLost


class LeaseHeartbeat:
    def __init__(self, jobs: DurableJobs, job: DurableJob) -> None:
        self.jobs, self.job = jobs, job
        self.stopped, self.lost = Event(), Event()
        self.thread = Thread(target=self._run, daemon=True, name="analysis-lease")

    def _run(self) -> None:
        while not self.stopped.wait(20):
            try:
                self.jobs.heartbeat(
                    self.job.request.analysis_id,
                    self.job.lease_owner,
                    self.job.fence,
                    datetime.now(UTC),
                )
            except Exception:
                self.lost.set()
                return

    def ensure(self) -> None:
        if self.lost.is_set():
            raise LeaseLost("worker could not maintain its execution lease")

    def __enter__(self) -> "LeaseHeartbeat":
        self.thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stopped.set()
        self.thread.join(timeout=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one persisted ClearCut analysis")
    parser.add_argument("--analysis-id", required=True)
    args = parser.parse_args()
    from clearcut.composition import _build_live_use_cases, _configure_telemetry, run_traced

    _configure_telemetry()
    graph = _build_live_use_cases()
    assert graph.durable_jobs is not None and graph.durable_analysis is not None
    owner = os.environ.get("CLOUD_RUN_EXECUTION") or "local-" + uuid4().hex
    pending = graph.durable_jobs.load(args.analysis_id)
    if pending.request.provider_config_json != graph.provider_config_json:
        graph = _build_live_use_cases(
            provider_config=json.loads(pending.request.provider_config_json)
        )
        assert graph.durable_jobs is not None and graph.durable_analysis is not None
    assert graph.durable_jobs is not None and graph.durable_analysis is not None
    jobs = graph.durable_jobs
    runner = graph.durable_analysis
    job = jobs.claim(args.analysis_id, owner, datetime.now(UTC))
    if job is None:
        return
    with LeaseHeartbeat(jobs, job) as heartbeat:
        try:
            run_traced(job.request.script_id, lambda: runner.execute_claimed(job, heartbeat.ensure))
        except Exception:
            try:
                jobs.fail(
                    job.request.analysis_id,
                    job.lease_owner,
                    job.fence,
                    "analysis_failed",
                    datetime.now(UTC),
                    False,
                )
            except (AnalysisCancelled, LeaseLost):
                pass


if __name__ == "__main__":
    main()
