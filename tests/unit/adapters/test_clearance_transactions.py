"""Atomic event/outbox publication and stale producer writes, without cloud claims."""

from copy import deepcopy
from dataclasses import replace
from typing import Any

import pytest
from flask import Flask

from clearcut.adapters.demo.in_memory import (
    InMemoryNotifier,
    InMemoryScriptStore,
    InMemoryTrackerStore,
)
from clearcut.adapters.gcp.tracker import FirestoreTrackerStore
from clearcut.adapters.http.tracker import create_tracker_blueprint
from clearcut.application.get_tracker_item import GetTrackerItem
from clearcut.application.list_tracker_items import ListTrackerItems
from clearcut.application.resolve_finding import ResolveFinding
from clearcut.domain.identity import AccessDenied
from clearcut.domain.tracker import TrackerConflict, TrackerItem, TrackerState
from tests.unit.adapters.test_firestore_access import Client, Ref, Transaction


class AtomicTransaction(Transaction):
    def set(self, ref: Ref, data: Any) -> None:
        self.writes.append((ref.path, deepcopy(data)))

    def update(self, ref: Ref, data: Any) -> None:
        self.writes.append((ref.path, {**self.client.data[ref.path], **data}))

    def create(self, ref: Ref, data: Any) -> None:
        assert ref.path not in self.client.data
        self.writes.append((ref.path, deepcopy(data)))

    def _commit(self) -> None:
        self.client.data.update(self.writes)


class AtomicClient(Client):
    def transaction(self) -> AtomicTransaction:
        return AtomicTransaction(self)


def item() -> TrackerItem:
    return TrackerItem(
        "asset",
        "project",
        "finding",
        (1,),
        TrackerState.BLOCKED,
        "permission",
        "private contact",
        "",
        "private note",
        "2026-09-06T10:00:00Z",
        1,
    )


def store() -> tuple[AtomicClient, FirestoreTrackerStore]:
    client = AtomicClient()
    client.data = {
        "project_access/project": {
            "organization_id": "org",
            "grants": {"producer": "producer", "viewer": "viewer"},
        },
        "organizations/org/members/producer": {"active": True, "role": "producer"},
        "organizations/org/members/viewer": {"active": True, "role": "viewer"},
    }
    return client, FirestoreTrackerStore(client, InMemoryScriptStore())


def test_system_replay_is_idempotent_and_conflicting_payload_is_rejected():
    client, tracker = store()
    tracker.save([item()])
    before = deepcopy(client.data)
    tracker.save([item()])
    assert client.data == before
    with pytest.raises(TrackerConflict):
        tracker.save([replace(item(), contact="different")])
    assert client.data == before


def test_stale_human_change_cannot_overwrite_winner_or_append_an_event():
    client, tracker = store()
    tracker.save([item()])
    updated = item().transitioned_to(TrackerState.IN_PROGRESS, "2026-09-06T11:00:00Z")
    tracker.compare_save(updated, 1, "producer")
    before = deepcopy(client.data)
    with pytest.raises(TrackerConflict) as conflict:
        tracker.compare_save(
            item().transitioned_to(TrackerState.CLEARED, updated.updated_at), 1, "producer"
        )
    assert conflict.value.current_version == 2
    assert client.data == before
    event = client.data["project_access/project/clearances/asset/events/2"]
    assert event["actor"] == "producer" and event["previous_version"] == 1
    assert event["item"]["state"] == "IN_PROGRESS"
    assert client.data["project_access/project"]["clearance_epoch"] == 2
    outbox = client.data["outbox/clearance-project-asset-2"]
    assert outbox["organization_id"] == "org" and outbox["source_version"] == 2
    assert "private contact" not in str(outbox) and "private note" not in str(outbox)


def test_revoked_membership_and_viewer_are_denied_in_commit_transaction():
    client, tracker = store()
    tracker.save([item()])
    client.data["organizations/org/members/producer"]["active"] = False
    before = deepcopy(client.data)
    for actor in ["producer", "viewer", "other-org-user"]:
        with pytest.raises(AccessDenied):
            tracker.compare_save(item().transitioned_to(TrackerState.CLEARED, "later"), 1, actor)
    assert client.data == before


def test_multi_item_conflict_does_not_publish_partial_batch():
    client, tracker = store()
    tracker.save([item()])
    before = deepcopy(client.data)
    with pytest.raises(TrackerConflict):
        tracker.save([replace(item(), item_id="new"), replace(item(), version=3)])
    assert client.data == before


def test_http_requires_expected_version_and_returns_conflict_for_late_actions():
    tracker = InMemoryTrackerStore()
    tracker.save([item()])
    app = Flask(__name__)
    app.register_blueprint(
        create_tracker_blueprint(
            ListTrackerItems(tracker),
            GetTrackerItem(tracker),
            ResolveFinding(tracker, InMemoryNotifier(), tracker),
        )
    )
    client = app.test_client()
    path = "/api/projects/project/tracker-items/asset"
    assert client.patch(path, json={"state": "CLEARED"}).status_code == 400
    assert client.post(path + "/email-drafts", json={"expected_version": True}).status_code == 400
    result = client.patch(path, json={"state": "IN_PROGRESS", "expected_version": 1})
    assert result.status_code == 200 and result.get_json()["version"] == 2
    stale = client.post(path + "/email-drafts", json={"expected_version": 1})
    assert stale.status_code == 409 and stale.get_json()["current_version"] == 2
    history = client.get(path + "/history")
    assert history.status_code == 200 and len(history.get_json()) == 1
    assert history.get_json()[0]["actor"] == "demo"
    assert client.get(path + "/history?before_version=2").json == []
    assert tracker.latest("project", "asset").draft_email is None


def test_evidence_and_assignment_are_validated_before_any_clearance_write():
    client, tracker = store()
    tracker.save([item()])
    before = deepcopy(client.data)
    from clearcut.domain.errors import RecordNotFound

    with pytest.raises(RecordNotFound):
        tracker.compare_save(
            replace(item(), version=2, evidence_file_ids=("foreign",)), 1, "producer"
        )
    with pytest.raises(AccessDenied):
        tracker.compare_save(
            replace(item(), version=2, assignee_id="other-workspace"), 1, "producer"
        )
    assert client.data == before
    client.data["project_access/project/documents/proof"] = {
        "project_id": "project",
        "organization_id": "org",
        "sha256": "immutable-sha",
    }
    updated = replace(
        item(),
        version=2,
        evidence_file_ids=("proof",),
        assignee_id="producer",
        due_date="2026-09-08",
        clearance_conditions="Only the signed territory and term",
    )
    tracker.compare_save(updated, 1, "producer")
    assert tracker.latest("project", "asset") == updated
    assert tracker.latest("project", "asset").state is TrackerState.BLOCKED
    assert client.data["project_access/project/clearances/asset/events/2"]["item"][
        "evidence_file_ids"
    ] == ["proof"]


def test_details_http_preserves_state_and_rejects_cross_project_evidence():
    from clearcut.adapters.demo.documents import MemoryProjectDocuments
    from clearcut.adapters.documents.permission_export import permission_document
    from clearcut.adapters.http.clearance_details import create_clearance_details_blueprint

    documents = MemoryProjectDocuments()
    evidence = documents.put(
        "org", "project", "proof.txt", "text/plain", b"permission", "evidence", "demo", "now"
    )
    foreign = documents.put(
        "elsewhere", "other", "private.txt", "text/plain", b"private", "evidence", "other", "now"
    )
    tracker = InMemoryTrackerStore()
    tracker.save([item()])
    app = Flask(__name__)
    app.register_blueprint(
        create_clearance_details_blueprint(
            ResolveFinding(tracker, InMemoryNotifier(), tracker),
            documents,
            GetTrackerItem(tracker),
            permission_document,
        )
    )
    client = app.test_client()
    path = "/api/projects/project/tracker-items/asset/details"
    payload = {
        "expected_version": 1,
        "note": "Signed release",
        "clearance_conditions": "Argentina; one feature film",
        "due_date": "2026-09-08",
        "assignee_id": "",
        "evidence_file_ids": [foreign.file_id],
        "draft_email": "Dear rights holder, may we...",
    }
    assert client.put(path, json=payload).status_code == 404
    assert tracker.latest("project", "asset").version == 1
    payload["evidence_file_ids"] = [evidence.file_id]
    result = client.put(path, json=payload)
    assert result.status_code == 200
    assert result.get_json()["state"] == "BLOCKED"
    assert result.get_json()["evidence_file_ids"] == [evidence.file_id]
    assert client.put(path, json=payload).status_code == 409
    download_path = "/api/projects/project/tracker-items/asset/permission-request"
    exported = client.get(download_path + "?version=2&format=txt")
    assert exported.status_code == 200
    assert b"Dear rights holder, may we..." in exported.data
    assert b"Argentina; one feature film" in exported.data
    assert exported.headers["Cache-Control"] == "no-store"
    assert client.get(download_path + "?version=1").status_code == 409
    payload["expected_version"] = 2
    payload["due_date"] = "2026-02-30"
    assert client.put(path, json=payload).status_code == 400
    assert tracker.latest("project", "asset").version == 2


def test_permission_pdf_escapes_markup_preserves_spanish_and_paginates():
    from io import BytesIO

    from pypdf import PdfReader

    from clearcut.adapters.documents.permission_export import permission_pdf

    draft = (
        "Estimado titular: ¿Podría autorizar música en México? <img src='https://example.invalid'>"
    )
    source = replace(
        item(),
        draft_email=(draft + "\n") * 60,
        clearance_conditions="Sólo Argentina y México; edición cinematográfica.",
    )
    reader = PdfReader(BytesIO(permission_pdf(source)))
    assert len(reader.pages) >= 2
    extracted = " ".join(page.extract_text() for page in reader.pages)
    assert "¿Podría autorizar música en México?" in extracted
    assert "<img src='https://example.invalid'>" in extracted
    assert "Sólo Argentina y México" in extracted
    assert "Draft only" in extracted


def test_human_generation_overlay_preserves_immutable_base_and_ignores_staged_rows():
    from clearcut.application.analysis_documents import tracker_data

    client, tracker = store()
    client.data["project_access/project"]["active_generation"] = "committed"
    base_path = "project_access/project/clearance_generations/committed/items/asset"
    client.data[base_path] = tracker_data(item())
    client.data["project_access/project/clearance_generations/staged/items/asset"] = tracker_data(
        replace(item(), note="unpublished result")
    )
    assert tracker.latest("project", "asset") == item()
    updated = replace(item(), version=2, note="producer's current decision")
    tracker.compare_save(updated, 1, "producer")
    assert tracker.latest("project", "asset") == updated
    assert client.data[base_path] == tracker_data(item())
    assert client.data[base_path + "/events/2"]["actor"] == "producer"
    assert client.data["project_access/project"]["clearance_epoch"] == 1
    with pytest.raises(TrackerConflict):
        tracker.compare_save(replace(item(), version=2, note="stale tab"), 1, "producer")
