"""Rebase publication, retained provider output and cancellation boundaries."""

from dataclasses import replace
from typing import Any

from clearcut.application.analysis_documents import finding_data, script_data, tracker_data
from clearcut.application.run_durable_analysis import RunDurableAnalysis
from clearcut.domain.durable_analysis import ClearanceSnapshot, DurableJob
from clearcut.domain.screenplay import ContentReference
from clearcut.domain.tracker import TrackerConflict, TrackerItem
from tests.unit.adapters.test_durable_jobs import NOW, configured
from tests.unit.application.test_analysis_checkpoints import Artifacts
from tests.unit.application.test_analyze_script import _AT, _MEXICO, _scene, _use_case


def test_publication_rebase_reuses_calculation_and_preserves_a_new_human_item():
    _, jobs, revision, command = configured()
    jobs.enqueue(command, revision)
    job = jobs.claim("analysis", "worker", NOW)
    assert job is not None
    report = _use_case().calculate(
        "project", "script", 1, "gs://revision", _MEXICO, _AT, [_scene()]
    )
    calls = []

    def calculate(job: DurableJob, steps: Any) -> dict[str, Any]:
        calls.append(job.request.analysis_id)
        return {
            "script": script_data(report.script),
            "findings": [finding_data(value) for value in report.findings],
            "tracker_items": [tracker_data(value) for value in report.tracker_items],
            "scene_anchors": [
                {"scene_number": 1, "scene_id": "stable", "content_digest": "content"}
            ],
        }

    class Publications:
        def __init__(self) -> None:
            self.epoch = 0
            self.items: list[TrackerItem] = []
            self.staged: list[list[TrackerItem]] = []

        def snapshot(self, project_id: str) -> tuple[ClearanceSnapshot, list[TrackerItem]]:
            return ClearanceSnapshot("", self.epoch, None), self.items

        def stage(
            self,
            job: DurableJob,
            baseline: ClearanceSnapshot,
            items: list[TrackerItem],
            manifest: ContentReference,
            previous_items: list[TrackerItem] | None = None,
        ) -> str:
            self.staged.append(items)
            return str(len(self.staged))

        def publish(
            self, job: DurableJob, baseline: ClearanceSnapshot, generation_id: str, at: Any
        ) -> DurableJob:
            if len(self.staged) == 1:
                self.items = [
                    replace(
                        report.tracker_items[0],
                        item_id="human-existing",
                        note="Concurrent producer note",
                        version=2,
                    )
                ]
                self.epoch = 1
                raise TrackerConflict(1)
            assert baseline.epoch == 1
            return replace(job, state="SUCCEEDED")

    publication = Publications()
    RunDurableAnalysis(
        jobs, Artifacts(), publication, publication, calculate, lambda: NOW
    ).execute_claimed(job)
    assert calls == ["analysis"] and len(publication.staged) == 2
    carried = next(item for item in publication.staged[1] if item.item_id == "human-existing")
    assert carried.note == "Concurrent producer note" and carried.needs_review


def test_cancellation_during_provider_work_prevents_calculated_checkpoint_and_publication():
    client, jobs, revision, command = configured()
    jobs.enqueue(command, revision)
    job = jobs.claim("analysis", "worker", NOW)
    assert job is not None

    def calculate(job: DurableJob, steps: Any) -> dict[str, Any]:
        jobs.request_cancel("project", "analysis", "writer", NOW)
        return {"provider": "finished after cancellation"}

    class Unreachable:
        def snapshot(self, project_id: str) -> tuple[ClearanceSnapshot, list[TrackerItem]]:
            raise AssertionError("cancelled analysis reached publication")

        def stage(
            self,
            job: DurableJob,
            baseline: ClearanceSnapshot,
            items: list[TrackerItem],
            manifest: ContentReference,
            previous_items: list[TrackerItem] | None = None,
        ) -> str:
            raise AssertionError("cancelled analysis staged results")

        def publish(
            self, job: DurableJob, baseline: ClearanceSnapshot, generation_id: str, at: Any
        ) -> DurableJob:
            raise AssertionError("cancelled analysis published results")

    unreachable = Unreachable()
    RunDurableAnalysis(
        jobs, Artifacts(), unreachable, unreachable, calculate, lambda: NOW
    ).execute_claimed(job)
    assert jobs.load("analysis").state == "CANCELLED"
    assert "analysis_jobs/analysis/checkpoints/calculated-result" not in client.data
