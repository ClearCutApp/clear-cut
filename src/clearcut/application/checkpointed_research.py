"""Resume known Parallel tasks; never resubmit an unknown create outcome."""

from dataclasses import asdict
from typing import Any

from clearcut.application.analysis_steps import AnalysisSteps
from clearcut.application.durable_ports import ResumableRightsResearch
from clearcut.application.ports import Confidence, RightsClaim
from clearcut.domain.durable_analysis import RetryAnalysis
from clearcut.domain.errors import EnrichmentMissing, SourceUnavailable
from clearcut.domain.finding import Category, Citation
from clearcut.domain.jurisdiction import Jurisdiction


def claim_data(claim: RightsClaim) -> dict[str, Any]:
    return {**asdict(claim), "confidence": claim.confidence.value}


def read_claim(value: dict[str, Any]) -> RightsClaim:
    return RightsClaim(
        **{
            **value,
            "confidence": Confidence(value["confidence"]),
            "citations": tuple(Citation(**citation) for citation in value.get("citations", [])),
        }
    )


class CheckpointedResearch:
    def __init__(self, provider: ResumableRightsResearch, steps: AnalysisSteps) -> None:
        self._provider, self._steps = provider, steps

    def find(self, asset_name: str, category: Category, jurisdiction: Jurisdiction) -> RightsClaim:
        steps = self._steps
        key = steps.key("research", [asset_name, category.value, jurisdiction.code])
        with steps.lock(key):
            steps.ensure("research")
            saved = steps.read(key)
            if saved:
                if saved.get("missing"):
                    steps.gaps[key] = {"stage": "research", "code": str(saved["missing"])}
                    raise EnrichmentMissing("rights-holder evidence unavailable")
                return read_claim(saved["value"])
            intent_key = "submission-" + key
            intent = steps.read(intent_key)
            if intent is None:
                steps.write(intent_key, {"state": "submitting"})
                try:
                    run_id = self._provider.begin(asset_name, category, jurisdiction)
                except SourceUnavailable:
                    steps.missing(key, "research", "research_submission_unknown")
                    raise EnrichmentMissing("research submission outcome unknown") from None
                steps.write(intent_key, {"state": "submitted", "run_id": run_id})
            elif intent.get("state") == "submitted" and intent.get("run_id"):
                run_id = str(intent["run_id"])
            else:
                steps.missing(key, "research", "research_submission_unknown")
                raise EnrichmentMissing("research submission outcome unknown")
            try:
                result = self._provider.await_result(run_id, asset_name)
            except EnrichmentMissing:
                steps.missing(key, "research")
                raise EnrichmentMissing("no cited rights holder found") from None
            except SourceUnavailable:
                raise RetryAnalysis("research is not yet available; resume the known run") from None
            steps.write(key, {"value": claim_data(result)})
            return result
