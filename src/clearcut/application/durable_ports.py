"""Durable execution and artifact boundaries used by HTTP, workers and dispatchers."""

from datetime import datetime
from typing import Any, Protocol

from clearcut.application.ports import RightsClaim
from clearcut.domain.durable_analysis import ClearanceSnapshot, DurableJob, NewAnalysis
from clearcut.domain.finding import Category
from clearcut.domain.jurisdiction import Jurisdiction
from clearcut.domain.screenplay import ContentReference, Revision
from clearcut.domain.tracker import TrackerItem


class AnalysisArtifacts(Protocol):
    def put(
        self,
        organization_id: str,
        project_id: str,
        analysis_id: str,
        kind: str,
        value: dict[str, Any],
    ) -> ContentReference: ...
    def get(self, reference: ContentReference) -> dict[str, Any]: ...
    def put_bytes(
        self,
        organization_id: str,
        project_id: str,
        analysis_id: str,
        kind: str,
        content: bytes,
        content_type: str,
    ) -> ContentReference: ...
    def get_bytes(self, reference: ContentReference) -> bytes: ...


class DurableJobs(Protocol):
    def current(self, project_id: str) -> DurableJob | None: ...
    def enqueue(self, command: NewAnalysis, revision: Revision) -> DurableJob: ...
    def get(self, project_id: str, analysis_id: str) -> DurableJob: ...
    def load(self, analysis_id: str) -> DurableJob: ...
    def claim(self, analysis_id: str, owner: str, at: datetime) -> DurableJob | None: ...
    def heartbeat(self, analysis_id: str, owner: str, fence: int, at: datetime) -> None: ...
    def progress(
        self, analysis_id: str, owner: str, fence: int, stage: str, at: datetime
    ) -> None: ...
    def checkpoint(
        self,
        analysis_id: str,
        owner: str,
        fence: int,
        key: str,
        reference: ContentReference,
        at: datetime,
    ) -> None: ...
    def read_checkpoint(self, analysis_id: str, key: str) -> ContentReference | None: ...
    def request_cancel(
        self, project_id: str, analysis_id: str, actor: str, at: datetime
    ) -> DurableJob: ...
    def fail(
        self, analysis_id: str, owner: str, fence: int, code: str, at: datetime, retryable: bool
    ) -> None: ...


class ResumableRightsResearch(Protocol):
    def begin(self, asset_name: str, category: Category, jurisdiction: Jurisdiction) -> str: ...
    def await_result(self, run_id: str, asset_name: str) -> RightsClaim: ...


class ClearanceGenerations(Protocol):
    def stage(
        self,
        job: DurableJob,
        baseline: ClearanceSnapshot,
        items: list[TrackerItem],
        manifest: ContentReference,
        previous_items: list[TrackerItem] | None = None,
    ) -> str: ...
    def publish(
        self, job: DurableJob, baseline: ClearanceSnapshot, generation_id: str, at: datetime
    ) -> DurableJob: ...


class ClearanceSnapshots(Protocol):
    def snapshot(self, project_id: str) -> tuple[ClearanceSnapshot, list[TrackerItem]]: ...


class AnalysisManifestReader(Protocol):
    def manifest(self, project_id: str, script_id: str) -> dict[str, Any]: ...
