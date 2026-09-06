"""The four new ClickHouse stores against ClickHouse Cloud (ADR 0014).

Each assertion here needs something only the server produces. A tuple that
comes back a tuple, a `Nullable(String)` that comes back `None`, a
`DateTime64(3, 'UTC')` that comes back a `datetime` at the millisecond the
domain wrote, and two rows that both survive `OPTIMIZE TABLE ... FINAL` are
all facts about ClickHouse's own serialization and merge. A hand-written fake
returns the object it was handed, so none of them would fail against one.

`ensure_schema()` runs first because nothing else creates the tables --
`composition.py` never calls it, so a live test that skips it fails on a
missing table rather than on anything meaningful.
"""

from datetime import UTC, datetime, timedelta
from typing import cast

import clickhouse_connect
import pytest

from clearcut.adapters.clickhouse.analyses import ClickHouseAnalysisJobStore
from clearcut.adapters.clickhouse.client import _ChClient, bare_host
from clearcut.adapters.clickhouse.findings import ClickHouseFindingStore
from clearcut.adapters.clickhouse.projects import ClickHouseProjectStore, ProjectNotFound
from clearcut.adapters.clickhouse.scripts import ClickHouseScriptStore, ScriptNotFound
from clearcut.domain.analysis import AnalysisJob, AnalysisState
from clearcut.domain.finding import Category, Citation, Finding, NerLabel, RiskLevel
from clearcut.domain.project import Project
from clearcut.domain.script import Scene, Script
from tests.live.conftest import env, requires, scratch_id

_CREDENTIALS = ("CLICKHOUSE_HOST", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD")


def _client() -> _ChClient:
    # cast: the same widening `composition.py` documents -- `Client.query`
    # returns rows one type wider than `_ChClient` declares, true at runtime
    # and invisible to mypy structurally.
    return cast(
        _ChClient,
        clickhouse_connect.get_client(
            host=bare_host(env("CLICKHOUSE_HOST")),
            username=env("CLICKHOUSE_USER"),
            password=env("CLICKHOUSE_PASSWORD"),
            secure=True,
        ),
    )


def _script(project_id: str, script_id: str, version: int) -> Script:
    return Script(
        script_id=script_id,
        project_id=project_id,
        version=version,
        gcs_uri=f"gs://clearcut-scripts/{project_id}/{script_id}.pdf",
        jurisdiction_code="AR",
        scenes=[
            Scene(
                number=12,
                heading="INT. BAR NOTTURNO - NIGHT",
                page_start=14,
                page_end=15,
                text=f"Mariana pushes the door open. Draft {version}.",
            )
        ],
    )


@pytest.mark.live
@requires(*_CREDENTIALS)
def test_a_project_survives_the_round_trip_with_its_accents_intact() -> None:
    """`title` is a ClickHouse `String`, which is bytes rather than text. A
    title that comes back with its accents is a title the server encoded and
    decoded as UTF-8 both ways."""
    store = ClickHouseProjectStore(_client())
    store.ensure_schema()
    project = Project(
        project_id=scratch_id("prj"),
        title="El Ultimo Verano de la Nina Mariana",
        jurisdiction_code="AR",
        created_at="2026-09-05T12:00:00Z",
    )

    store.save(project)

    assert store.get(project.project_id) == project
    assert project in store.all()


@pytest.mark.live
@requires(*_CREDENTIALS)
def test_an_unknown_project_raises_rather_than_returning_an_empty_row() -> None:
    store = ClickHouseProjectStore(_client())
    store.ensure_schema()

    with pytest.raises(ProjectNotFound):
        store.get(scratch_id("prj-absent"))


@pytest.mark.live
@requires(*_CREDENTIALS)
def test_two_script_versions_of_one_project_both_come_back() -> None:
    """`ORDER BY project_id` kept one row per project, so `for_project` could
    only ever return one entry. Forcing the merge is what proves the new key
    keeps both."""
    client = _client()
    store = ClickHouseScriptStore(client)
    store.ensure_schema()
    project_id = scratch_id("prj-scripts")
    first = _script(project_id, scratch_id("scr"), version=1)
    second = _script(project_id, scratch_id("scr"), version=2)

    store.save(first)
    store.save(second)
    client.command("OPTIMIZE TABLE script_versions FINAL")

    assert store.for_project(project_id) == [first, second]
    assert store.latest(project_id) == second
    assert store.get(project_id, first.script_id) == first


@pytest.mark.live
@requires(*_CREDENTIALS)
def test_an_unknown_script_raises_rather_than_returning_an_empty_row() -> None:
    store = ClickHouseScriptStore(_client())
    store.ensure_schema()

    with pytest.raises(ScriptNotFound):
        store.get(scratch_id("prj"), scratch_id("scr-absent"))


@pytest.mark.live
@requires(*_CREDENTIALS)
def test_a_bible_finding_reads_back_with_a_real_null_ner_label() -> None:
    """`ner_label` is `Nullable(String)`, and `Finding` raises if a
    `CONTINUITY` finding carries one. The server deciding to hand back the
    empty string instead of a null is what this catches; a fake hands back
    the `None` it was given either way."""
    client = _client()
    store = ClickHouseFindingStore(client)
    store.ensure_schema()
    project_id = scratch_id("prj-findings")
    script_id = scratch_id("scr")
    branded = Finding(
        finding_id="EVT-014",
        scene_number=12,
        page=14,
        raw_text="a Coca-Cola sign flickers above the bar",
        category=Category.INDUSTRIAL_PROPERTY,
        ner_label=NerLabel.BRAND,
        risk_level=RiskLevel.HIGH,
        required_document="Trademark Use Authorization",
        citations=(
            Citation(
                uri="https://servicios.infoleg.gob.ar/infolegInternet/anexos/42755/texact.htm",
                title="Ley 11.723",
                snippet="Articulo 1",
            ),
        ),
    )
    continuity = Finding(
        finding_id="EVT-015",
        scene_number=41,
        page=52,
        raw_text="Mariana mentions her year in Madrid",
        category=Category.CONTINUITY,
        ner_label=None,
        risk_level=RiskLevel.MEDIUM,
        required_document="Bible reconciliation",
        contradicts="FACT-007",
    )

    store.save(project_id, script_id, [branded, continuity])
    client.command("OPTIMIZE TABLE findings FINAL")

    stored = store.for_script(project_id, script_id)
    assert stored == [branded, continuity]
    assert stored[1].ner_label is None
    assert stored[0].citations[0].snippet == "Articulo 1"


@pytest.mark.live
@requires(*_CREDENTIALS)
def test_findings_of_one_version_never_leak_into_another() -> None:
    client = _client()
    store = ClickHouseFindingStore(client)
    store.ensure_schema()
    project_id = scratch_id("prj-versions")
    first_version = Finding(
        finding_id="EVT-001",
        scene_number=3,
        page=4,
        raw_text="a Rolex on the bar",
        category=Category.INDUSTRIAL_PROPERTY,
        ner_label=NerLabel.BRAND,
        risk_level=RiskLevel.MEDIUM,
        required_document="Trademark Use Authorization",
    )

    store.save(project_id, "scr-v1", [first_version])
    store.save(project_id, "scr-v2", [])
    client.command("OPTIMIZE TABLE findings FINAL")

    assert store.for_script(project_id, "scr-v1") == [first_version]
    assert store.for_script(project_id, "scr-v2") == []


@pytest.mark.live
@requires(*_CREDENTIALS)
def test_an_analysis_job_keeps_its_utc_instant_to_the_millisecond() -> None:
    """`DateTime64(3, 'UTC')` is the one column in this schema the driver
    parses rather than copies. The value below carries 250 milliseconds, so a
    column stored at second precision loses them and a naive value read back
    makes `is_stale` raise instead of answer."""
    store = ClickHouseAnalysisJobStore(_client())
    store.ensure_schema()
    created = datetime(2026, 9, 5, 12, 0, 0, tzinfo=UTC)
    updated = datetime(2026, 9, 5, 12, 4, 11, 250000, tzinfo=UTC)
    project_id = scratch_id("prj-analyses")
    job = AnalysisJob(
        analysis_id=scratch_id("ana"),
        project_id=project_id,
        script_id=scratch_id("scr"),
        state=AnalysisState.RUNNING,
        created_at=created,
        updated_at=updated,
    )

    store.save(job)

    stored = store.get(project_id, job.analysis_id)
    assert stored == job
    assert stored.updated_at == updated
    assert stored.updated_at.tzinfo is not None
    assert stored.is_stale(updated + timedelta(minutes=31), timedelta(minutes=30))


@pytest.mark.live
@requires(*_CREDENTIALS)
def test_the_newest_transition_of_a_job_is_the_one_that_reads_back() -> None:
    """Every transition writes a new versioned row, so the read has to pick
    the highest version out of what the server returns rather than the first
    row it sees."""
    client = _client()
    store = ClickHouseAnalysisJobStore(client)
    store.ensure_schema()
    project_id = scratch_id("prj-transitions")
    started = datetime(2026, 9, 5, 12, 0, 0, tzinfo=UTC)
    queued = AnalysisJob(
        analysis_id=scratch_id("ana"),
        project_id=project_id,
        script_id=scratch_id("scr"),
        state=AnalysisState.QUEUED,
        created_at=started,
        updated_at=started,
    )
    running = queued.running(started + timedelta(seconds=2))
    succeeded = running.succeeded(started + timedelta(minutes=9))

    store.save(queued)
    store.save(succeeded)
    store.save(running)
    client.command("OPTIMIZE TABLE analysis_jobs FINAL")

    assert store.get(project_id, queued.analysis_id) == succeeded
