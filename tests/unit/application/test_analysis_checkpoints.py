"""Provider creation ambiguity and persisted-result retry behavior."""

from typing import Any

import pytest

from clearcut.application.analysis_documents import canonical, digest
from clearcut.application.analysis_steps import AnalysisSteps
from clearcut.application.checkpointed_research import CheckpointedResearch
from clearcut.application.ports import Confidence, RightsClaim
from clearcut.domain.durable_analysis import RetryAnalysis
from clearcut.domain.errors import EnrichmentMissing, SourceUnavailable
from clearcut.domain.finding import Category
from clearcut.domain.jurisdiction import Jurisdiction, jurisdiction_for
from clearcut.domain.screenplay import ContentReference
from tests.unit.adapters.test_durable_jobs import NOW, configured


class Artifacts:
    def __init__(self) -> None:
        self.values: dict[str, dict[str, Any]] = {}

    def put(
        self,
        organization_id: str,
        project_id: str,
        analysis_id: str,
        kind: str,
        value: dict[str, Any],
    ) -> ContentReference:
        key = digest(value)
        self.values[key] = value
        return ContentReference(key, key, len(canonical(value)))

    def get(self, reference: ContentReference) -> dict[str, Any]:
        return self.values[reference.uri]

    def put_bytes(
        self,
        organization_id: str,
        project_id: str,
        analysis_id: str,
        kind: str,
        content: bytes,
        content_type: str,
    ) -> ContentReference:
        raise AssertionError("unexpected byte operation")

    def get_bytes(self, reference: ContentReference) -> bytes:
        raise AssertionError("unexpected byte operation")


class Research:
    def __init__(self, *, ambiguous: bool = False, delayed: bool = False) -> None:
        self.creates = 0
        self.polls: list[str] = []
        self.ambiguous, self.delayed = ambiguous, delayed

    def begin(self, asset_name: str, category: Category, jurisdiction: Jurisdiction) -> str:
        self.creates += 1
        if self.ambiguous:
            raise SourceUnavailable("unknown response")
        return "known-run"

    def await_result(self, run_id: str, asset_name: str) -> RightsClaim:
        self.polls.append(run_id)
        if self.delayed and len(self.polls) == 1:
            raise SourceUnavailable("not ready")
        return RightsClaim("Holder", "contact", "unknown", Confidence.HIGH)


def steps() -> AnalysisSteps:
    _, jobs, revision, command = configured()
    jobs.enqueue(command, revision)
    job = jobs.claim("analysis", "worker", NOW)
    assert job is not None
    return AnalysisSteps(job, jobs, Artifacts(), lambda: NOW)


def test_unknown_creation_response_is_never_submitted_twice():
    state = steps()
    provider = Research(ambiguous=True)
    for _ in range(2):
        research = CheckpointedResearch(provider, state)
        with pytest.raises(EnrichmentMissing):
            research.find("Brand", Category.INDUSTRIAL_PROPERTY, jurisdiction_for("AR"))
    assert provider.creates == 1 and provider.polls == []
    assert next(iter(state.gaps.values()))["code"] == "research_submission_unknown"


def test_known_run_timeout_resumes_polling_without_recreating_task():
    state = steps()
    provider = Research(delayed=True)
    research = CheckpointedResearch(provider, state)
    with pytest.raises(RetryAnalysis):
        research.find("Brand", Category.INDUSTRIAL_PROPERTY, jurisdiction_for("AR"))
    result = CheckpointedResearch(provider, state).find(
        "Brand", Category.INDUSTRIAL_PROPERTY, jurisdiction_for("AR")
    )
    cached = CheckpointedResearch(provider, state).find(
        "Brand", Category.INDUSTRIAL_PROPERTY, jurisdiction_for("AR")
    )
    assert result == cached and result.holder == "Holder"
    assert provider.creates == 1 and provider.polls == ["known-run", "known-run"]


def test_crash_after_submission_intent_does_not_guess_that_create_failed():
    state = steps()
    country = jurisdiction_for("AR")
    key = state.key("research", ["Brand", Category.INDUSTRIAL_PROPERTY.value, country.code])
    state.write("submission-" + key, {"state": "submitting"})
    provider = Research()
    with pytest.raises(EnrichmentMissing):
        CheckpointedResearch(provider, state).find("Brand", Category.INDUSTRIAL_PROPERTY, country)
    assert provider.creates == 0 and provider.polls == []
