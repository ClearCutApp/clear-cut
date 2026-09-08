"""Only a committed generation may become visible; fake transactions, no live claim."""

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import timedelta
from typing import Any

import pytest

from clearcut.adapters.gcp.clearance_generations import FirestoreClearanceGenerations
from clearcut.domain.durable_analysis import AnalysisCancelled, ClearanceSnapshot, LeaseLost
from clearcut.domain.screenplay import ContentReference
from clearcut.domain.tracker import TrackerConflict
from tests.unit.adapters.test_clearance_transactions import item
from tests.unit.adapters.test_durable_jobs import NOW, configured
from tests.unit.adapters.test_firestore_access import Ref


@pytest.mark.parametrize("large_details", [False, True])
def test_generation_staging_preserves_more_than_150_items_without_exposing_them(
    monkeypatch, large_details
):
    client, jobs, revision, command = configured()
    jobs.enqueue(command, revision)
    job = jobs.claim("analysis", "worker", NOW)
    assert job is not None

    def create(ref: Ref, data: Any) -> None:
        assert ref.path not in ref.client.data
        ref.client.data[ref.path] = deepcopy(data)

    def update(ref: Ref, data: Any) -> None:
        ref.client.data[ref.path].update(data)

    sizes: list[int] = []

    class Batch:
        def __init__(self) -> None:
            self.rows: list[tuple[Ref, Any]] = []

        def create(self, ref: Ref, data: Any) -> None:
            self.rows.append((ref, data))

        def commit(self) -> None:
            sizes.append(len(self.rows))
            for ref, data in self.rows:
                create(ref, data)

    monkeypatch.setattr(Ref, "create", create, raising=False)
    monkeypatch.setattr(Ref, "update", update, raising=False)
    monkeypatch.setattr(client, "batch", Batch, raising=False)
    generations = FirestoreClearanceGenerations(client)
    baseline = ClearanceSnapshot("", 0, None)
    manifest = ContentReference("gs://bucket/manifest", "hash", 100)
    source = item()
    if large_details:
        source = replace(
            source, draft_email="界" * 20000, note="界" * 4000, clearance_conditions="界" * 4000
        )
    generation = generations.stage(
        job,
        baseline,
        [replace(source, item_id=f"item-{number}") for number in range(701)],
        manifest,
    )
    assert sum(sizes) == 1402  # Immutable item plus its first analysis audit event.
    assert max(sizes) < 100 if large_details else max(sizes) == 400
    assert not client.data["project_access/project"].get("active_generation")
    assert "lore_outbox/analysis" not in client.data
    completed = generations.publish(job, baseline, generation, NOW)
    assert completed.state == "SUCCEEDED"
    assert client.data["project_access/project"]["active_generation"] == generation
    assert client.data["outbox/analysis-analysis"]["payload"]["item_count"] == 701
    projection = client.data["lore_outbox/analysis"]
    assert projection["manifest"] == asdict(manifest)
    assert projection["revision_id"] == revision.revision_id and projection["state"] == "pending"
    before = deepcopy(client.data)
    assert generations.publish(job, baseline, generation, NOW) == completed
    assert client.data == before


@pytest.mark.parametrize("race", ["human_edit", "cancel", "new_lease", "incomplete"])
def test_publication_races_cannot_expose_partial_results(race):
    client, jobs, revision, command = configured()
    jobs.enqueue(command, revision)
    job = jobs.claim("analysis", "worker", NOW)
    assert job is not None
    baseline = ClearanceSnapshot("", 0, None)
    client.data["project_access/project/clearance_generations/staged"] = {
        "state": "ready",
        "analysis_id": "analysis",
        "organization_id": "org",
        "parent_generation": "",
        "baseline_epoch": 0,
        "item_count": 1,
        "manifest": asdict(revision.content),
    }
    at = NOW
    expected: type[Exception]
    if race == "human_edit":
        client.data["project_access/project"]["clearance_epoch"] = 1
        expected = TrackerConflict
    elif race == "cancel":
        jobs.request_cancel("project", "analysis", "writer", NOW)
        expected = AnalysisCancelled
    elif race == "new_lease":
        at = NOW + timedelta(seconds=91)
        jobs.claim("analysis", "replacement", at)
        expected = LeaseLost
    else:
        client.data["project_access/project/clearance_generations/staged"]["state"] = "staging"
        expected = ValueError
    before = deepcopy(client.data)
    with pytest.raises(expected):
        FirestoreClearanceGenerations(client).publish(job, baseline, "staged", at)
    assert client.data == before
    assert "outbox/analysis-analysis" not in client.data
    assert "lore_outbox/analysis" not in client.data
