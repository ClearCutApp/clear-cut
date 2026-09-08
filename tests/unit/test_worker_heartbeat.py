"""A renewal failure stops new paid stage work without waiting for lease expiry."""

from typing import Any

import pytest

from clearcut.application.analysis_steps import AnalysisSteps
from clearcut.application.checkpointed_research import CheckpointedResearch
from clearcut.domain.durable_analysis import LeaseLost
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.finding import Category
from clearcut.domain.jurisdiction import jurisdiction_for
from clearcut.worker import LeaseHeartbeat
from tests.unit.adapters.test_durable_jobs import NOW, configured
from tests.unit.application.test_analysis_checkpoints import Artifacts, Research


def test_failed_renewal_prevents_another_provider_submission(monkeypatch):
    _, jobs, revision, command = configured()
    jobs.enqueue(command, revision)
    job = jobs.claim("analysis", "worker", NOW)
    assert job is not None
    heartbeat = LeaseHeartbeat(jobs, job)

    def unavailable(*args: Any) -> None:
        raise SourceUnavailable("renewal unavailable")

    monkeypatch.setattr(jobs, "heartbeat", unavailable)
    monkeypatch.setattr(heartbeat.stopped, "wait", lambda seconds: False)
    heartbeat._run()
    provider = Research()
    steps = AnalysisSteps(job, jobs, Artifacts(), lambda: NOW, heartbeat.ensure)
    with pytest.raises(LeaseLost):
        CheckpointedResearch(provider, steps).find(
            "Brand", Category.INDUSTRIAL_PROPERTY, jurisdiction_for("AR")
        )
    assert provider.creates == 0
