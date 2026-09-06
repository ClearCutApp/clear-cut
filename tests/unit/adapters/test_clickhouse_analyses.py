"""Unit tests for the ClickHouse-backed `AnalysisJobStore` (ADR 0013, 0014).

An upload answers 202 and the browser polls this row, so it is the only thing
that knows whether a run that started is still running.

`AnalysisJob` carries timezone-aware `datetime` values and the column is
`DateTime64(3, 'UTC')`. The adapter owns both directions of that conversion:
`is_stale` subtracts two datetimes, and a naive one read back from the driver
would raise on the subtraction rather than answer it. The tests below pin the
awareness, not only the value.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from clearcut.adapters.clickhouse.analyses import (
    AnalysisJobNotFound,
    ClickHouseAnalysisJobStore,
    _job_to_row,
)
from clearcut.adapters.clickhouse.client import ClickHouseUnavailable
from clearcut.application.ports import AnalysisJobStore
from clearcut.domain.analysis import AnalysisJob, AnalysisState
from tests.unit.adapters.fake_ch_client import ExplodingChClient, FakeChClient

_CREATED = datetime(2026, 9, 5, 12, 0, 0, tzinfo=UTC)
_UPDATED = datetime(2026, 9, 5, 12, 4, 11, 250000, tzinfo=UTC)


def _job(
    analysis_id: str = "ana-91c3",
    project_id: str = "prj-4f2a",
    script_id: str = "scr-77b1",
    state: AnalysisState = AnalysisState.RUNNING,
    error: str = "",
    version: int = 1,
) -> AnalysisJob:
    return AnalysisJob(
        analysis_id=analysis_id,
        project_id=project_id,
        script_id=script_id,
        state=state,
        created_at=_CREATED,
        updated_at=_UPDATED,
        error=error,
        version=version,
    )


def test_adapter_satisfies_the_analysisjobstore_port() -> None:
    adapter = ClickHouseAnalysisJobStore(FakeChClient())
    checked: AnalysisJobStore = adapter
    assert isinstance(checked, AnalysisJobStore)


def test_ensure_schema_keys_jobs_on_the_project_and_the_analysis() -> None:
    client = FakeChClient()

    ClickHouseAnalysisJobStore(client).ensure_schema()

    ddl = next(cmd for cmd in client.commands if "CREATE TABLE IF NOT EXISTS analysis_jobs" in cmd)
    assert "ORDER BY (project_id, analysis_id)" in ddl
    assert "ReplacingMergeTree(version)" in ddl
    assert "DateTime64(3, 'UTC')" in ddl


def test_save_hands_clickhouse_datetimes_never_strings() -> None:
    """The column is a timestamp, so the driver gets a `datetime`. A string
    here would store the ISO text in a `DateTime64` column and fail at the
    boundary rather than in a test."""
    client = FakeChClient()

    ClickHouseAnalysisJobStore(client).save(_job())

    table, rows, columns = client.inserts[0]
    assert table == "analysis_jobs"
    assert isinstance(rows[0][columns.index("created_at")], datetime)
    assert isinstance(rows[0][columns.index("updated_at")], datetime)


def test_get_returns_the_stored_job_at_its_highest_version() -> None:
    client = FakeChClient()
    adapter = ClickHouseAnalysisJobStore(client)
    queued = _job(state=AnalysisState.QUEUED, version=1)
    running = _job(state=AnalysisState.RUNNING, version=3)
    finished = _job(state=AnalysisState.SUCCEEDED, version=2)
    # The highest version sits in the middle: neither "first row wins" nor
    # "last row wins" finds it, only a real max-version comparison does.
    client.set_result(
        [tuple(_job_to_row(queued)), tuple(_job_to_row(running)), tuple(_job_to_row(finished))]
    )

    result = adapter.get("prj-4f2a", "ana-91c3")

    assert result.version == 3
    assert result.state is AnalysisState.RUNNING


def test_get_reads_back_timezone_aware_datetimes() -> None:
    client = FakeChClient()
    adapter = ClickHouseAnalysisJobStore(client)
    client.set_result([tuple(_job_to_row(_job()))])

    result = adapter.get("prj-4f2a", "ana-91c3")

    assert result.created_at == _CREATED
    assert result.updated_at == _UPDATED
    assert result.updated_at.tzinfo is not None
    assert result.is_stale(_UPDATED + timedelta(minutes=31), timedelta(minutes=30))


def test_get_attaches_utc_to_a_naive_datetime_the_driver_hands_back() -> None:
    """`clickhouse_connect` returns a naive `datetime` unless the connection
    is configured otherwise, and `is_stale` subtracts it from an aware `now`
    -- which raises `TypeError` rather than answering. The adapter attaches
    the timezone the column already declares."""
    client = FakeChClient()
    adapter = ClickHouseAnalysisJobStore(client)
    row = list(_job_to_row(_job()))
    row[4] = _CREATED.replace(tzinfo=None)
    row[5] = _UPDATED.replace(tzinfo=None)
    client.set_result([tuple(row)])

    result = adapter.get("prj-4f2a", "ana-91c3")

    assert result.created_at == _CREATED
    assert result.updated_at == _UPDATED


def test_get_ignores_a_job_belonging_to_another_project() -> None:
    client = FakeChClient()
    adapter = ClickHouseAnalysisJobStore(client)
    client.set_result([tuple(_job_to_row(_job(project_id="prj-other")))])

    with pytest.raises(AnalysisJobNotFound):
        adapter.get("prj-4f2a", "ana-91c3")


def test_get_raises_not_found_naming_both_ids() -> None:
    client = FakeChClient()
    adapter = ClickHouseAnalysisJobStore(client)
    client.set_result([])

    with pytest.raises(AnalysisJobNotFound) as excinfo:
        adapter.get("prj-4f2a", "ana-missing")

    assert "ana-missing" in str(excinfo.value)
    assert "prj-4f2a" in str(excinfo.value)


def test_a_failed_job_round_trips_its_reason() -> None:
    client = FakeChClient()
    adapter = ClickHouseAnalysisJobStore(client)
    failed = _job(state=AnalysisState.FAILED, error="Document AI returned no pages", version=2)
    client.set_result([tuple(_job_to_row(failed))])

    assert adapter.get("prj-4f2a", "ana-91c3") == failed


def test_ensure_schema_wraps_a_client_error_as_clickhouse_unavailable() -> None:
    with pytest.raises(ClickHouseUnavailable):
        ClickHouseAnalysisJobStore(ExplodingChClient()).ensure_schema()


def test_save_wraps_a_client_error_as_clickhouse_unavailable() -> None:
    with pytest.raises(ClickHouseUnavailable):
        ClickHouseAnalysisJobStore(ExplodingChClient()).save(_job())


def test_get_wraps_a_client_error_as_clickhouse_unavailable() -> None:
    with pytest.raises(ClickHouseUnavailable):
        ClickHouseAnalysisJobStore(ExplodingChClient()).get("prj-4f2a", "ana-91c3")
