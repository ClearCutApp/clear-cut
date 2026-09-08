"""Firestore execution leases and checkpoints; callbacks contain no provider calls."""

import json
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from typing import Any, Callable

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from clearcut.application.analysis_documents import read_job
from clearcut.domain.analysis_lifecycle import (
    cancel_job,
    claim_job,
    fail_job,
    renew_job,
    require_lease,
)
from clearcut.domain.durable_analysis import AnalysisBusy, AnalysisRequest, DurableJob, NewAnalysis
from clearcut.domain.errors import RecordNotFound, SourceUnavailable
from clearcut.domain.identity import AccessDenied, project_permits
from clearcut.domain.screenplay import ContentReference, Revision


class FirestoreAnalysisJobs:
    def __init__(self, client: Any) -> None:
        self.client = client

    def reference(self, analysis_id: str) -> Any:
        if not analysis_id or any(char in analysis_id for char in "/\\"):
            raise RecordNotFound("analysis not found")
        return self.client.collection("analysis_jobs").document(analysis_id)

    def enqueue(self, command: NewAnalysis, revision: Revision) -> DurableJob:
        project_ref = self.client.collection("project_access").document(command.project_id)
        ref = self.reference(command.analysis_id)

        @firestore.transactional
        def write(transaction: Any) -> DurableJob:
            project = project_ref.get(transaction=transaction).to_dict() or {}
            member = (
                self.client.collection("organizations")
                .document(command.organization_id)
                .collection("members")
                .document(command.actor)
                .get(transaction=transaction)
                .to_dict()
                or {}
            )
            saved_revision = (
                project_ref.collection("revisions")
                .document(command.revision_id)
                .get(transaction=transaction)
                .to_dict()
            )
            existing = ref.get(transaction=transaction).to_dict()
            active_id = project.get("active_analysis")
            active = (
                self.reference(active_id).get(transaction=transaction).to_dict()
                if active_id
                else None
            )
            if project.get("organization_id") != command.organization_id or not project_permits(
                project, member, command.actor, "script"
            ):
                raise AccessDenied("project analysis access required")
            if (
                revision.project_id != command.project_id
                or revision.revision_id != command.revision_id
                or saved_revision != asdict(revision)
            ):
                raise RecordNotFound("saved revision not found")
            if existing:
                previous = read_job(existing)
                if (
                    previous.request.project_id != command.project_id
                    or previous.request.revision_id != command.revision_id
                    or previous.request.actor != command.actor
                ):
                    raise AnalysisBusy("analysis identity already used")
                return previous
            if active and not read_job(active).terminal:
                raise AnalysisBusy("a project analysis is already active")
            request = AnalysisRequest(
                **asdict(command),
                revision_content=revision.content,
                revision_version=revision.draft_version,
                settings_version=int(project.get("settings_version", 1)),
                script_version=int(project.get("analysis_sequence", 0)) + 1,
                production_context_json=json.dumps(
                    {
                        **json.loads(project.get("production_context_json", "{}")),
                        "analysis_jurisdiction": command.jurisdiction_code,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                baseline_generation=project.get("active_generation", ""),
                baseline_manifest=ContentReference(**project["analysis_manifest"])
                if project.get("analysis_manifest")
                else None,
            )
            job = DurableJob(
                request, "QUEUED", "queued", command.created_at, available_at=command.created_at
            )
            transaction.create(ref, asdict(job))
            transaction.update(
                project_ref,
                {
                    "active_analysis": command.analysis_id,
                    "analysis_sequence": request.script_version,
                },
            )
            transaction.create(
                self.client.collection("analysis_launches").document(command.analysis_id),
                {
                    "analysis_id": command.analysis_id,
                    "project_id": command.project_id,
                    "state": "pending",
                    "created_at": command.created_at,
                },
            )
            return job

        result: DurableJob = write(self.client.transaction())
        return result

    def load(self, analysis_id: str) -> DurableJob:
        try:
            data = self.reference(analysis_id).get().to_dict()
        except RecordNotFound:
            raise
        except Exception as exc:
            raise SourceUnavailable("analysis lookup unavailable") from exc
        if not data:
            raise RecordNotFound("analysis not found")
        return read_job(data)

    def get(self, project_id: str, analysis_id: str) -> DurableJob:
        job = self.load(analysis_id)
        if job.request.project_id != project_id:
            raise RecordNotFound("analysis not found")
        return job

    def current(self, project_id: str) -> DurableJob | None:
        project = (
            self.client.collection("project_access").document(project_id).get().to_dict() or {}
        )
        analysis_id = project.get("active_analysis") or project.get("committed_analysis_id")
        return self.get(project_id, analysis_id) if analysis_id else None

    def _change(
        self, analysis_id: str, change: Callable[[DurableJob], DurableJob | None]
    ) -> DurableJob | None:
        ref = self.reference(analysis_id)

        @firestore.transactional
        def write(transaction: Any) -> DurableJob | None:
            data = ref.get(transaction=transaction).to_dict()
            if not data:
                raise RecordNotFound("analysis not found")
            previous = read_job(data)
            updated = change(previous)
            if updated is not None and updated != previous:
                transaction.update(ref, asdict(updated))
            return updated

        return write(self.client.transaction())  # type: ignore[no-any-return]

    def claim(self, analysis_id: str, owner: str, at: datetime) -> DurableJob | None:
        result = self._change(analysis_id, lambda job: claim_job(job, owner, at))
        return result if result and result.state == "RUNNING" else None

    def heartbeat(self, analysis_id: str, owner: str, fence: int, at: datetime) -> None:
        self._change(analysis_id, lambda job: renew_job(job, owner, fence, at))

    def progress(self, analysis_id: str, owner: str, fence: int, stage: str, at: datetime) -> None:
        def change(job: DurableJob) -> DurableJob:
            require_lease(job, owner, fence, at)
            return replace(job, stage=stage, updated_at=at)

        self._change(analysis_id, change)

    def checkpoint(
        self,
        analysis_id: str,
        owner: str,
        fence: int,
        key: str,
        reference: ContentReference,
        at: datetime,
    ) -> None:
        ref = self.reference(analysis_id)
        if not key or any(char in key for char in "/\\"):
            raise ValueError("invalid checkpoint key")

        @firestore.transactional
        def write(transaction: Any) -> None:
            data = ref.get(transaction=transaction).to_dict()
            if not data:
                raise RecordNotFound("analysis not found")
            require_lease(read_job(data), owner, fence, at)
            transaction.set(ref.collection("checkpoints").document(key), asdict(reference))

        write(self.client.transaction())

    def read_checkpoint(self, analysis_id: str, key: str) -> ContentReference | None:
        data = self.reference(analysis_id).collection("checkpoints").document(key).get().to_dict()
        return ContentReference(**data) if data else None

    def request_cancel(
        self, project_id: str, analysis_id: str, actor: str, at: datetime
    ) -> DurableJob:
        ref = self.reference(analysis_id)
        project_ref = self.client.collection("project_access").document(project_id)

        @firestore.transactional
        def write(transaction: Any) -> DurableJob:
            data = ref.get(transaction=transaction).to_dict()
            project = project_ref.get(transaction=transaction).to_dict() or {}
            if not data or not project.get("organization_id"):
                raise RecordNotFound("analysis not found")
            job = read_job(data)
            member = (
                self.client.collection("organizations")
                .document(project["organization_id"])
                .collection("members")
                .document(actor)
                .get(transaction=transaction)
                .to_dict()
                or {}
            )
            if job.request.project_id != project_id:
                raise RecordNotFound("analysis not found")
            if not project_permits(project, member, actor, "script"):
                raise AccessDenied("project analysis access required")
            updated = cancel_job(job, at)
            transaction.update(ref, {**asdict(updated), "cancelled_by": actor})
            return updated

        result: DurableJob = write(self.client.transaction())
        return result

    def fail(
        self, analysis_id: str, owner: str, fence: int, code: str, at: datetime, retryable: bool
    ) -> None:
        self._change(analysis_id, lambda job: fail_job(job, owner, fence, code, at, retryable))

    def ready(self, at: datetime, limit: int = 50) -> list[str]:
        collection = self.client.collection("analysis_jobs")
        result: list[str] = []
        for state, field in (("QUEUED", "available_at"), ("RUNNING", "lease_until")):
            query = (
                collection.where(filter=FieldFilter("state", "==", state))
                .where(filter=FieldFilter(field, "<=", at))
                .order_by(field)
                .limit(limit)
            )
            result.extend(row.to_dict()["request"]["analysis_id"] for row in query.stream())
        return list(dict.fromkeys(result))[:limit]

    def reserve_launch(self, analysis_id: str, owner: str, at: datetime) -> bool:
        job_ref = self.reference(analysis_id)
        launch_ref = self.client.collection("analysis_launches").document(analysis_id)

        @firestore.transactional
        def write(transaction: Any) -> bool:
            data = job_ref.get(transaction=transaction).to_dict()
            launch = launch_ref.get(transaction=transaction).to_dict() or {}
            if not data:
                return False
            job = read_job(data)
            if (
                job.terminal
                or job.cancel_requested
                or (job.lease_until and job.lease_until > at)
                or (job.available_at and job.available_at > at)
            ):
                return False
            if launch.get("reserved_until") and launch["reserved_until"] > at:
                return False
            transaction.set(
                launch_ref,
                {
                    **launch,
                    "analysis_id": analysis_id,
                    "state": "launching",
                    "owner": owner,
                    "reserved_until": at + timedelta(minutes=2),
                    "attempt": int(launch.get("attempt", 0)) + 1,
                },
            )
            return True

        result: bool = write(self.client.transaction())
        return result

    def acknowledge_launch(self, analysis_id: str, owner: str, operation: str) -> None:
        ref = self.client.collection("analysis_launches").document(analysis_id)

        @firestore.transactional
        def write(transaction: Any) -> None:
            launch = ref.get(transaction=transaction).to_dict() or {}
            if launch.get("owner") == owner:
                transaction.update(ref, {"state": "launched", "operation": operation})

        write(self.client.transaction())
