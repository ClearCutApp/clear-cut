"""Final report publication checks the same snapshot and current permissions."""

from copy import deepcopy
from dataclasses import asdict, replace

import pytest

from clearcut.adapters.gcp.reports import FirestoreReports
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.identity import AccessDenied
from clearcut.domain.report import ClearanceReport, ReportConflict
from tests.unit.adapters.test_clearance_transactions import AtomicClient
from tests.unit.adapters.test_durable_jobs import NOW, configured


def ready_report() -> tuple[AtomicClient, FirestoreReports, ClearanceReport]:
    client, jobs, revision, command = configured()
    jobs.enqueue(command, revision)
    job = jobs.load("analysis")
    client.data["analysis_jobs/analysis"] = asdict(
        replace(job, state="SUCCEEDED", generation_id="generation", result=revision.content)
    )
    client.data["project_access/project"].update(
        {
            "grants": {"writer": "producer"},
            "active_generation": "generation",
            "clearance_epoch": 2,
            "committed_analysis_id": "analysis",
            "analysis_manifest": asdict(revision.content),
        }
    )
    report = ClearanceReport(
        "report",
        "project",
        "org",
        "analysis",
        "revision-1",
        "generation",
        2,
        "writer",
        NOW.isoformat(),
        "es",
        revision.content,
        revision.content,
        revision.content,
        revision.content,
        {"total_retained": 3, "confirmed_cleared": 1},
    )
    return client, FirestoreReports(client), report


def test_published_report_replay_is_idempotent_and_later_edits_do_not_change_it():
    client, reports, report = ready_report()
    reports.publish(report)
    before = deepcopy(client.data)
    reports.publish(report)
    assert client.data == before
    client.data["project_access/project"]["clearance_epoch"] = 3
    assert reports.get("project", "report") == report
    with pytest.raises(RecordNotFound):
        reports.get("another-project", "report")
    assert client.data["outbox/report-report"]["payload"]["counts"]["confirmed_cleared"] == 1


@pytest.mark.parametrize("race", ["epoch", "generation", "revision", "revoked", "unassigned"])
def test_changed_snapshot_or_access_prevents_any_report_or_outbox_publication(race):
    client, reports, report = ready_report()
    expected: type[Exception] = ReportConflict
    if race == "epoch":
        client.data["project_access/project"]["clearance_epoch"] = 3
    elif race == "generation":
        client.data["project_access/project"]["active_generation"] = "new-generation"
    elif race == "revision":
        client.data["analysis_jobs/analysis"]["request"]["revision_id"] = "other-revision"
    elif race == "revoked":
        client.data["organizations/org/members/writer"]["active"] = False
        expected = AccessDenied
    else:
        client.data["project_access/project"]["grants"] = {}
        expected = AccessDenied
    before = deepcopy(client.data)
    with pytest.raises(expected):
        reports.publish(report)
    assert client.data == before


@pytest.mark.parametrize("changed", ["research", "settings", "context"])
def test_research_or_location_change_prevents_report_publication(changed):
    from hashlib import sha256

    client, reports, report = ready_report()
    report = replace(
        report,
        production_context_sha256=sha256(b"{}").hexdigest(),
        local_research_epoch=0,
        settings_version=1,
    )
    scope = client.data["project_access/project"]
    if changed == "research":
        scope["local_research_epoch"] = 1
    if changed == "settings":
        scope["settings_version"] = 2
    if changed == "context":
        scope["production_context_json"] = '{"locations":[]}'
    before = deepcopy(client.data)
    with pytest.raises(ReportConflict):
        reports.publish(report)
    assert client.data == before
