"""Persist completed provider work; retries never replay published side effects."""

from collections.abc import Callable
from datetime import datetime
from threading import Lock
from typing import Any, TypeVar

from clearcut.application.analysis_documents import digest
from clearcut.application.durable_ports import AnalysisArtifacts, DurableJobs
from clearcut.domain.durable_analysis import DurableJob, RetryAnalysis
from clearcut.domain.errors import EnrichmentMissing, SourceUnavailable

T = TypeVar("T")


class AnalysisSteps:
    def __init__(
        self,
        job: DurableJob,
        jobs: DurableJobs,
        artifacts: AnalysisArtifacts,
        clock: Callable[[], datetime],
        guard: Callable[[], None] = lambda: None,
    ) -> None:
        self.job, self.jobs, self.artifacts, self.clock = job, jobs, artifacts, clock
        self.guard = guard
        self._locks: dict[str, Any] = {}
        self._guard = Lock()
        self.gaps: dict[str, dict[str, str]] = {}

    def key(self, stage: str, inputs: Any) -> str:
        return stage + "-" + digest(inputs)

    def lock(self, key: str) -> Any:
        with self._guard:
            return self._locks.setdefault(key, Lock())

    def ensure(self, stage: str) -> None:
        self.guard()
        self.jobs.progress(
            self.job.request.analysis_id, self.job.lease_owner, self.job.fence, stage, self.clock()
        )

    def read(self, key: str) -> dict[str, Any] | None:
        reference = self.jobs.read_checkpoint(self.job.request.analysis_id, key)
        return self.artifacts.get(reference) if reference else None

    def write(self, key: str, value: dict[str, Any]) -> None:
        self.guard()
        request = self.job.request
        reference = self.artifacts.put(
            request.organization_id, request.project_id, request.analysis_id, "checkpoint", value
        )
        self.jobs.checkpoint(
            request.analysis_id, self.job.lease_owner, self.job.fence, key, reference, self.clock()
        )

    def missing(self, key: str, stage: str, code: str = "no_cited_evidence") -> None:
        self.write(key, {"missing": code})
        with self._guard:
            self.gaps[key] = {"stage": stage, "code": code}

    def run(
        self,
        stage: str,
        inputs: Any,
        call: Callable[[], T],
        encode: Callable[[T], dict[str, Any]],
        decode: Callable[[dict[str, Any]], T],
    ) -> T:
        key = self.key(stage, inputs)
        with self.lock(key):
            self.ensure(stage)
            saved = self.read(key)
            if saved:
                if saved.get("missing"):
                    with self._guard:
                        self.gaps[key] = {"stage": stage, "code": str(saved["missing"])}
                    raise EnrichmentMissing("no cited evidence available")
                return decode(saved["value"])
            try:
                result = call()
            except EnrichmentMissing:
                self.missing(key, stage)
                raise EnrichmentMissing("no cited evidence available") from None
            except SourceUnavailable:
                raise RetryAnalysis("provider unavailable; resume persisted checkpoints") from None
            self.write(key, {"value": encode(result)})
            return result
