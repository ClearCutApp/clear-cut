"""Persists analysis jobs over ClickHouse (ADR 0013, ADR 0014).

A script upload answers 202 and hands back an analysis id, so this row is the
only thing that knows whether a run that started is still running. Every
transition writes a new row at `version + 1`, the same latest-wins read the
tracker uses, which is why the engine keeps its version argument here and the
project sits ahead of the analysis in the sort key.

`AnalysisJob.created_at` and `updated_at` are timezone-aware `datetime`
values and the columns are `DateTime64(3, 'UTC')`. This module owns both
directions of that conversion: the domain never sees a string, and it never
sees a naive datetime either, because `is_stale` subtracts `updated_at` from
a caller-supplied `now` and mixing a naive value into that subtraction raises
`TypeError` instead of answering the question.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from clearcut.adapters.clickhouse import client as ch_client
from clearcut.adapters.clickhouse import schema
from clearcut.domain.analysis import AnalysisJob, AnalysisState
from clearcut.domain.errors import RecordNotFound

ANALYSIS_JOB_COLUMNS = [
    "analysis_id",
    "project_id",
    "script_id",
    "state",
    "created_at",
    "updated_at",
    "error",
    "version",
]


class AnalysisJobNotFound(RecordNotFound):
    """No stored row exists for the requested project and `analysis_id`."""

    def __init__(self, project_id: str, analysis_id: str) -> None:
        super().__init__(
            f"no analysis found for project_id={project_id!r} analysis_id={analysis_id!r}"
        )
        self.project_id = project_id
        self.analysis_id = analysis_id


class ClickHouseAnalysisJobStore:
    """Implements `AnalysisJobStore` over a ClickHouse Cloud HTTPS connection."""

    def __init__(self, client: ch_client._ChClient) -> None:
        self._client = client

    def ensure_schema(self) -> None:
        schema.ensure_schema(self._client)

    def save(self, job: AnalysisJob) -> None:
        try:
            self._client.insert("analysis_jobs", [_job_to_row(job)], ANALYSIS_JOB_COLUMNS)
        except Exception as exc:
            raise ch_client.ClickHouseUnavailable(
                f"failed to save analysis {job.analysis_id!r}: {exc}"
            ) from exc

    def get(self, project_id: str, analysis_id: str) -> AnalysisJob:
        try:
            result = self._client.query(
                "SELECT * FROM analysis_jobs "
                "WHERE project_id = {project_id:String} "
                "AND analysis_id = {analysis_id:String}",
                {"project_id": project_id, "analysis_id": analysis_id},
            )
        except Exception as exc:
            raise ch_client.ClickHouseUnavailable(f"failed to query analysis_jobs: {exc}") from exc
        project_index = ANALYSIS_JOB_COLUMNS.index("project_id")
        matching = [
            row
            for row in result.result_rows
            if row[0] == analysis_id and row[project_index] == project_id
        ]
        if not matching:
            raise AnalysisJobNotFound(project_id, analysis_id)
        version_index = ANALYSIS_JOB_COLUMNS.index("version")
        return _row_to_job(max(matching, key=lambda row: row[version_index]))


def _job_to_row(job: AnalysisJob) -> list[Any]:
    return [
        job.analysis_id,
        job.project_id,
        job.script_id,
        job.state.value,
        job.created_at,
        job.updated_at,
        job.error,
        job.version,
    ]


def _row_to_job(row: tuple[Any, ...]) -> AnalysisJob:
    values = dict(zip(ANALYSIS_JOB_COLUMNS, row, strict=True))
    return AnalysisJob(
        analysis_id=values["analysis_id"],
        project_id=values["project_id"],
        script_id=values["script_id"],
        state=AnalysisState(values["state"]),
        created_at=_as_utc(values["created_at"]),
        updated_at=_as_utc(values["updated_at"]),
        error=values["error"],
        version=int(values["version"]),
    )


def _as_utc(stored: datetime) -> datetime:
    """The stored timestamp as a timezone-aware UTC `datetime`.

    `clickhouse_connect` returns a naive value for a `DateTime64` column
    unless the connection is configured to do otherwise, and that setting is
    the composition root's to choose, not this module's to depend on. The
    column declares UTC, so a naive reading is UTC with the label missing.
    """
    if stored.tzinfo is None:
        return stored.replace(tzinfo=UTC)
    return stored.astimezone(UTC)
