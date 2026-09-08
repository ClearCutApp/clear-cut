"""Locations are versioned and copied into analysis requests, never read later."""

import json
from dataclasses import asdict, replace

import pytest

from clearcut.adapters.gcp.drafts import FirestoreDraftStore
from clearcut.adapters.gcp.project_settings import FirestoreProjectSettings
from clearcut.domain.identity import AccessDenied
from clearcut.domain.screenplay import Draft
from clearcut.domain.workspace import ProductionLocation, ProjectSettings, WorkspaceConflict
from tests.unit.adapters.test_durable_jobs import NOW, configured


def test_settings_cas_and_frozen_analysis_context_survive_later_location_changes():
    client, jobs, revision, command = configured()
    client.data["project_access/project"]["grants"]["writer"] = "producer"
    client.data["projects/project"] = {
        "title": "Film",
        "jurisdiction_code": "AR",
        "created_at": NOW.isoformat(),
    }
    settings = FirestoreProjectSettings(client)
    next_settings = ProjectSettings(
        "project",
        "Film",
        "AR",
        2,
        (ProductionLocation("AR", "Buenos Aires, exterior near the public plaza"),),
    )
    settings.save("writer", next_settings, 1, NOW)
    with pytest.raises(WorkspaceConflict):
        settings.save("writer", next_settings, 1, NOW)
    job = jobs.enqueue(command, revision)
    saved_context = json.loads(job.request.production_context_json)
    assert saved_context["locations"][0]["location"].startswith("Buenos Aires")
    assert saved_context["analysis_jurisdiction"] == "AR" and job.request.settings_version == 2
    settings.save(
        "writer",
        replace(
            next_settings, version=3, locations=(ProductionLocation("MX", "Ciudad de México"),)
        ),
        2,
        NOW,
    )
    assert (
        jobs.load("analysis").request.production_context_json == job.request.production_context_json
    )
    assert settings.get("project").version == 3


def test_rejoined_membership_cannot_write_existing_drafts_or_project_settings():
    client, _, revision, _ = configured()
    client.data["organizations/org/members/writer"]["membership_epoch"] = 2
    client.data["project_access/project/drafts/current"] = asdict(
        Draft("project", 1, revision.content, "writer", NOW.isoformat())
    )
    client.data["projects/project"] = {"title": "Film", "jurisdiction_code": "AR"}
    drafts = FirestoreDraftStore(client)
    with pytest.raises(AccessDenied):
        drafts.save("project", 1, revision.content, "writer", NOW.isoformat())
    with pytest.raises(AccessDenied):
        drafts.freeze("project", 1, "writer", NOW.isoformat())
    with pytest.raises(AccessDenied):
        FirestoreProjectSettings(client).save(
            "writer", ProjectSettings("project", "Film", "AR", 2), 1, NOW
        )
