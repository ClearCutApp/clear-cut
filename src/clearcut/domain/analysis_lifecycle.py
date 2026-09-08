"""Pure lease transitions; persistence must apply them inside a transaction."""

from dataclasses import replace
from datetime import datetime, timedelta

from clearcut.domain.durable_analysis import AnalysisCancelled, DurableJob, LeaseLost

LEASE_SECONDS = 90
MAX_ATTEMPTS = 4


def require_lease(job: DurableJob, owner: str, fence: int, at: datetime) -> None:
    if job.cancel_requested or job.state == "CANCELLED":
        raise AnalysisCancelled("analysis cancellation requested")
    if (
        job.state != "RUNNING"
        or job.lease_owner != owner
        or job.fence != fence
        or job.lease_until is None
        or job.lease_until <= at
    ):
        raise LeaseLost("analysis execution lease expired or was replaced")


def claim_job(job: DurableJob, owner: str, at: datetime) -> DurableJob | None:
    if not owner:
        raise ValueError("worker identity is required")
    if job.terminal or job.cancel_requested:
        return None
    if job.available_at is not None and job.available_at > at:
        return None
    if job.state == "RUNNING" and job.lease_until and job.lease_until > at:
        return None
    if job.attempt >= MAX_ATTEMPTS:
        return replace(
            job,
            state="FAILED",
            stage="failed",
            error_code="retry_limit",
            lease_owner="",
            lease_until=None,
            updated_at=at,
        )
    return replace(
        job,
        state="RUNNING",
        attempt=job.attempt + 1,
        fence=job.fence + 1,
        lease_owner=owner,
        lease_until=at + timedelta(seconds=LEASE_SECONDS),
        updated_at=at,
        error_code="",
        available_at=None,
    )


def renew_job(job: DurableJob, owner: str, fence: int, at: datetime) -> DurableJob:
    require_lease(job, owner, fence, at)
    return replace(job, lease_until=at + timedelta(seconds=LEASE_SECONDS), updated_at=at)


def cancel_job(job: DurableJob, at: datetime) -> DurableJob:
    if job.terminal:
        return job
    return replace(
        job,
        state="CANCELLED",
        stage="cancelled",
        cancel_requested=True,
        lease_owner="",
        lease_until=None,
        updated_at=at,
    )


def fail_job(
    job: DurableJob, owner: str, fence: int, code: str, at: datetime, retryable: bool
) -> DurableJob:
    require_lease(job, owner, fence, at)
    retry = retryable and job.attempt < MAX_ATTEMPTS
    return replace(
        job,
        state="QUEUED" if retry else "FAILED",
        stage="retrying" if retry else "failed",
        lease_owner="",
        lease_until=None,
        error_code=code,
        updated_at=at,
        available_at=at + timedelta(seconds=min(300, 15 * 2 ** (job.attempt - 1)))
        if retry
        else None,
    )
