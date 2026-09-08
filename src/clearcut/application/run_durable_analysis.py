"""Resume provider checkpoints and publish a complete, human-edit-safe generation."""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from clearcut.application.analysis_documents import (
    finding_data,
    read_finding,
    read_script,
    read_tracker,
    tracker_data,
)
from clearcut.application.analysis_steps import AnalysisSteps
from clearcut.application.analyze_script import AnalysisReport
from clearcut.application.durable_ports import (
    AnalysisArtifacts,
    ClearanceGenerations,
    ClearanceSnapshots,
    DurableJobs,
)
from clearcut.application.reconcile_analysis import reconcile_analysis
from clearcut.domain.durable_analysis import AnalysisCancelled, DurableJob, LeaseLost, RetryAnalysis
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.tracker import TrackerConflict


class RunDurableAnalysis:
    def __init__(
        self,
        jobs: DurableJobs,
        artifacts: AnalysisArtifacts,
        snapshots: ClearanceSnapshots,
        generations: ClearanceGenerations,
        calculate: Callable[[DurableJob, AnalysisSteps], dict[str, Any]],
        clock: Callable[[], datetime],
    ) -> None:
        self.jobs, self.artifacts = jobs, artifacts
        self.snapshots, self.generations = snapshots, generations
        self.calculate, self.clock = calculate, clock

    def execute_claimed(self, job: DurableJob, guard: Callable[[], None] = lambda: None) -> None:
        steps = AnalysisSteps(job, self.jobs, self.artifacts, self.clock, guard)
        request = job.request
        try:
            steps.ensure("preparing")
            raw = steps.read("calculated-result")
            if raw is None:
                raw = self.calculate(job, steps)
                steps.write("calculated-result", raw)
            report = AnalysisReport(
                read_script(raw["script"]),
                tuple(read_finding(value) for value in raw["findings"]),
                tuple(read_tracker(value) for value in raw["tracker_items"]),
            )
            for _ in range(3):
                steps.ensure("publishing")
                baseline, current = self.snapshots.snapshot(request.project_id)
                previous = self.artifacts.get(baseline.manifest) if baseline.manifest else None
                findings, items, bindings = reconcile_analysis(
                    report,
                    current,
                    previous,
                    raw["scene_anchors"],
                    request.revision_id,
                    request.production_context_json,
                    self.clock().isoformat(),
                )
                manifest = {
                    **raw,
                    "findings": [finding_data(item) for item in findings],
                    "tracker_items": [tracker_data(item) for item in items],
                    "clearance_bindings": bindings,
                    "baseline_epoch": baseline.epoch,
                    "production_context_json": request.production_context_json,
                    "settings_version": request.settings_version,
                }
                reference = self.artifacts.put(
                    request.organization_id,
                    request.project_id,
                    request.analysis_id,
                    "result",
                    manifest,
                )
                generation = self.generations.stage(job, baseline, items, reference, current)
                try:
                    self.generations.publish(job, baseline, generation, self.clock())
                    return
                except TrackerConflict:
                    continue
            raise RetryAnalysis("clearance state changed during publication")
        except (AnalysisCancelled, LeaseLost):
            return
        except (RetryAnalysis, SourceUnavailable):
            self._fail(job, "temporarily_unavailable", True)

    def _fail(self, job: DurableJob, code: str, retryable: bool) -> None:
        try:
            self.jobs.fail(
                job.request.analysis_id, job.lease_owner, job.fence, code, self.clock(), retryable
            )
        except (AnalysisCancelled, LeaseLost):
            return
