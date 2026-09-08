"""Stage complete generations, then expose one pointer in a fenced transaction."""

from dataclasses import asdict, replace
from datetime import datetime
from typing import Any
from uuid import uuid4

from google.cloud import firestore

from clearcut.application.analysis_documents import canonical, digest, read_job, tracker_data
from clearcut.domain.activity import activity_envelope
from clearcut.domain.analysis_lifecycle import require_lease
from clearcut.domain.durable_analysis import ClearanceSnapshot, DurableJob
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.report import clearance_counts
from clearcut.domain.screenplay import ContentReference
from clearcut.domain.tracker import TrackerConflict, TrackerItem


class FirestoreClearanceGenerations:
    def __init__(self, client: Any) -> None:
        self.client = client

    def project(self, project_id: str) -> Any:
        return self.client.collection("project_access").document(project_id)

    def generation(self, project_id: str, generation_id: str) -> Any:
        return self.project(project_id).collection("clearance_generations").document(generation_id)

    def stage(
        self,
        job: DurableJob,
        baseline: ClearanceSnapshot,
        items: list[TrackerItem],
        manifest: ContentReference,
        previous_items: list[TrackerItem] | None = None,
    ) -> str:
        request = job.request
        if len({item.item_id for item in items}) != len(items) or any(
            item.project_id != request.project_id for item in items
        ):
            raise ValueError("generation items must have unique IDs in one project")
        generation_id = uuid4().hex
        ref = self.generation(request.project_id, generation_id)
        rows = sorted(items, key=lambda item: item.item_id)
        previous = {item.item_id: item for item in previous_items or []}
        if not set(previous).issubset({item.item_id for item in rows}):
            raise ValueError("a generation must retain every prior clearance item")
        metadata = {
            "state": "staging",
            "analysis_id": request.analysis_id,
            "organization_id": request.organization_id,
            "parent_generation": baseline.generation_id,
            "baseline_epoch": baseline.epoch,
            "item_count": len(rows),
            "counts": {
                key: value
                for key, value in clearance_counts(rows, {}).items()
                if key not in {"present", "not_detected", "unknown_binding"}
            },
            "items_hash": digest([tracker_data(item) for item in rows]),
            "manifest": asdict(manifest),
        }
        ref.create(metadata)
        # Reserve room for protobuf field names/document paths and transaction
        # overhead below the 10 MiB request and 1 MiB document limits.
        batch = self.client.batch()
        count, size = 0, 0
        for item in rows:
            data = tracker_data(item)
            item_ref = ref.collection("items").document(item.item_id)
            writes = [(item_ref, data)]
            old = previous.get(item.item_id)
            if old != item:
                if item.version != (old.version if old else 0) + 1:
                    raise ValueError("changed clearance versions must advance exactly once")
                event_id = f"clearance-{request.project_id}-{item.item_id}-{item.version}"
                writes.append(
                    (
                        item_ref.collection("events").document(str(item.version)),
                        {
                            "event_id": event_id,
                            "actor": "analysis",
                            "version": item.version,
                            "previous_version": old.version if old else 0,
                            "at": item.updated_at,
                            "item": data,
                        },
                    )
                )
            for destination, value in writes:
                row_size = len(canonical(value)) + 4096
                if row_size > 900_000:
                    raise ValueError("one clearance item exceeds the document storage limit")
                if count and (count >= 400 or size + row_size > 8 * 1024 * 1024):
                    batch.commit()
                    batch, count, size = self.client.batch(), 0, 0
                batch.create(destination, value)
                count += 1
                size += row_size
        if count:
            batch.commit()
        ref.update({"state": "ready"})
        return generation_id

    def publish(
        self, job: DurableJob, baseline: ClearanceSnapshot, generation_id: str, at: datetime
    ) -> DurableJob:
        request = job.request
        project_ref = self.project(request.project_id)
        generation_ref = self.generation(request.project_id, generation_id)
        job_ref = self.client.collection("analysis_jobs").document(request.analysis_id)

        @firestore.transactional
        def write(transaction: Any) -> DurableJob:
            project = project_ref.get(transaction=transaction).to_dict() or {}
            generation = generation_ref.get(transaction=transaction).to_dict() or {}
            data = job_ref.get(transaction=transaction).to_dict()
            if not data:
                raise RecordNotFound("analysis not found")
            current = read_job(data)
            if current.state == "SUCCEEDED" and current.generation_id == generation_id:
                return current
            require_lease(current, job.lease_owner, job.fence, at)
            if (
                project.get("active_generation", "") != baseline.generation_id
                or int(project.get("clearance_epoch", 0)) != baseline.epoch
            ):
                raise TrackerConflict(int(project.get("clearance_epoch", 0)))
            if (
                generation.get("state") != "ready"
                or generation.get("analysis_id") != request.analysis_id
                or generation.get("organization_id") != request.organization_id
                or generation.get("parent_generation") != baseline.generation_id
                or generation.get("baseline_epoch") != baseline.epoch
                or project.get("active_analysis") != request.analysis_id
                or project.get("organization_id") != request.organization_id
            ):
                raise ValueError("generation is not ready for this analysis")
            manifest = ContentReference(**generation["manifest"])
            completed = replace(
                current,
                state="SUCCEEDED",
                stage="complete",
                result=manifest,
                generation_id=generation_id,
                lease_until=None,
                lease_owner="",
                updated_at=at,
            )
            transaction.update(generation_ref, {"state": "committed", "committed_at": at})
            transaction.update(job_ref, asdict(completed))
            transaction.update(
                project_ref,
                {
                    "active_generation": generation_id,
                    "clearance_epoch": baseline.epoch + 1,
                    "analysis_manifest": asdict(manifest),
                    "active_analysis": "",
                    "committed_analysis_id": request.analysis_id,
                },
            )
            transaction.create(
                project_ref.collection("analyzed_scripts").document(request.script_id),
                {
                    "script_id": request.script_id,
                    "analysis_id": request.analysis_id,
                    "revision_id": request.revision_id,
                    "version": request.script_version,
                    "manifest": asdict(manifest),
                    "created_at": at,
                },
            )
            event_id = "analysis-" + request.analysis_id
            payload = {
                "analysis_id": request.analysis_id,
                "revision_id": request.revision_id,
                "generation_id": generation_id,
                "item_count": generation["item_count"],
                "counts": generation["counts"],
            }
            transaction.create(
                self.client.collection("outbox").document(event_id),
                {
                    **activity_envelope(
                        event_id,
                        request.organization_id,
                        request.project_id,
                        "analysis_published",
                        at,
                        request.script_version,
                        payload,
                    ),
                    "manifest": asdict(manifest),
                },
            )
            transaction.create(
                self.client.collection("lore_outbox").document(request.analysis_id),
                {
                    "analysis_id": request.analysis_id,
                    "organization_id": request.organization_id,
                    "project_id": request.project_id,
                    "revision_id": request.revision_id,
                    "manifest": asdict(manifest),
                    "provider_config_json": request.provider_config_json,
                    "state": "pending",
                    "cursor": 0,
                    "attempt": 0,
                    "available_at": at,
                    "created_at": at,
                },
            )
            return completed

        result: DurableJob = write(self.client.transaction())
        return result
