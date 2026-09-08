"""Resolves a rights holder through the Parallel Task API (docs/plan/sdd.md
Section 3, docs/plan/infrastructure.md Section 7).

The task's output schema asks for a list of candidate `claims`, one per
possible rights holder Parallel's research turned up. The Task API's `basis`
carries citations and a confidence value per top-level field, indexed as
`claims.0`, `claims.1`, and so on for list elements. This adapter returns the
first claim whose basis entry carries a citation and drops the rest: an
uncited rights holder is not something the tracker can act on
(docs/plan/agentic-workflow.md Section 3).

Turning a claim's confidence into a finding's risk level is `AnalyzeScript`'s
rule (docs/plan/sdd.md Section 4.1 step 5), not this adapter's — it only
reports the `Confidence` Parallel gave the field.
"""

from __future__ import annotations

import time

import httpx
from opentelemetry import metrics, trace
from parallel import APIConnectionError, APIResponseValidationError, APIStatusError, Parallel
from parallel.types.citation import Citation as ParallelCitation
from parallel.types.field_basis import FieldBasis
from parallel.types.json_schema_param import JsonSchemaParam
from parallel.types.task_run_json_output import TaskRunJsonOutput
from parallel.types.task_run_result import TaskRunResult
from parallel.types.task_spec_param import TaskSpecParam

from clearcut.application.ports import Confidence, RightsClaim
from clearcut.domain.errors import EnrichmentMissing, SourceUnavailable
from clearcut.domain.finding import Category, Citation
from clearcut.domain.jurisdiction import Jurisdiction
from clearcut.observability import stage_span

# "core" is sized for a cross-referenced lookup (ASCAP/BMI Songview, SADAIC,
# label sites) inside the demo clock (docs/plan/infrastructure.md Section
# 7.1). It has never varied, so it is not a constructor argument (AGENT.md
# Section 4).
_PROCESSOR = "core"

_OUTPUT_SCHEMA: JsonSchemaParam = {
    "type": "json",
    "json_schema": {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "holder": {"type": "string"},
                        "contact": {"type": "string"},
                        "litigation_posture": {"type": "string"},
                    },
                    "required": ["holder", "contact", "litigation_posture"],
                },
            },
        },
        "required": ["claims"],
    },
}
_TASK_SPEC: TaskSpecParam = {"output_schema": _OUTPUT_SCHEMA}


def _record_stage(stage: str, start: float) -> None:
    """CP-031 (ADR 0008, SDD Section 6); see `adapters/gcp/document_ai.py`
    for why the tracer/meter lookups happen fresh on every call."""
    duration_ms = (time.perf_counter() - start) * 1000
    metrics.get_meter(__name__).create_histogram(
        "clearcut_stage_latency_ms", unit="ms", description="Pipeline stage latency"
    ).record(duration_ms, {"stage": stage})


class NoRightsHolderFound(EnrichmentMissing):
    """Raised when every candidate claim in a Task API result is uncited."""

    def __init__(self, asset_name: str) -> None:
        super().__init__("no cited rights holder found")
        self.asset_name = asset_name


class ResearchUnavailable(SourceUnavailable):
    """Raised when the Parallel Task API could not be reached, timed out, or
    responded with a non-2xx status."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ParallelRightsResearch:
    """Implements `RightsResearch` over the Parallel Task API."""

    def __init__(
        self,
        http_client: httpx.Client,
        api_key: str,
        *,
        create_timeout: float = 30,
        result_timeout: float = 300,
        processor: str = _PROCESSOR,
    ) -> None:
        # max_retries=0: a retry hides a transport failure behind exponential
        # backoff sleeps, which unit tests cannot afford and which would
        # leave a use case waiting well past the demo clock in production
        # (AGENT.md Section 5, docs/plan/infrastructure.md Section 7.1).
        # _strict_response_validation=True: the SDK defaults to lenient, which
        # hands back a bare `str` when a proxy answers 200 with an HTML
        # interstitial. The `AttributeError` on the next use of that value is
        # mapped to 500 by `adapters/http/errors.py`, reporting an upstream
        # outage as a ClearCut bug (ADR 0011, CP-056).
        self._create_timeout = create_timeout
        self._result_timeout = result_timeout
        self._processor = processor
        self._client = Parallel(
            api_key=api_key,
            http_client=http_client,
            max_retries=0,
            _strict_response_validation=True,
        )

    def find(self, asset_name: str, category: Category, jurisdiction: Jurisdiction) -> RightsClaim:
        stage_start = time.perf_counter()
        with stage_span(trace.get_tracer(__name__), "research"):
            claim = self._find(asset_name, category, jurisdiction)
        _record_stage("research", stage_start)
        return claim

    def _find(self, asset_name: str, category: Category, jurisdiction: Jurisdiction) -> RightsClaim:
        return self.await_result(self.begin(asset_name, category, jurisdiction), asset_name)

    def begin(self, asset_name: str, category: Category, jurisdiction: Jurisdiction) -> str:
        """Create once; durable callers persist intent before this boundary."""
        try:
            run = self._client.task_run.create(
                input=_query(asset_name, category, jurisdiction),
                processor=self._processor,
                task_spec=_TASK_SPEC,
                timeout=self._create_timeout,
            )
            if not run.run_id:
                raise ResearchUnavailable(
                    "Parallel Task API accepted the run but returned no run_id"
                )
            return str(run.run_id)
        except APIResponseValidationError as error:
            raise ResearchUnavailable("Parallel Task API returned an invalid response") from error
        except APIStatusError as error:
            raise ResearchUnavailable(
                f"Parallel Task API responded with status {error.status_code}",
                status_code=error.status_code,
            ) from error
        except APIConnectionError as error:
            raise ResearchUnavailable("Parallel Task API request failed") from error

    def await_result(self, run_id: str, asset_name: str) -> RightsClaim:
        """Resume polling a persisted run ID; this method never creates a task."""
        try:
            result = self._client.task_run.result(
                run_id,
                api_timeout=max(1, int(self._result_timeout) - 5),
                timeout=self._result_timeout,
            )
        except APIResponseValidationError as error:
            raise ResearchUnavailable("Parallel Task API returned an invalid response") from error
        except APIStatusError as error:
            raise ResearchUnavailable(
                f"Parallel Task API responded with status {error.status_code}",
                status_code=error.status_code,
            ) from error
        except APIConnectionError as error:
            raise ResearchUnavailable("Parallel Task API request failed") from error
        return _first_cited_claim(result, asset_name)


def _query(asset_name: str, category: Category, jurisdiction: Jurisdiction) -> str:
    label = category.value.replace("_", " ").lower()
    return (
        f"Who owns the {label} rights to '{asset_name}' in "
        f"{jurisdiction.display_name}? Who represents them, and do they have "
        "a record of litigation over similar uses?"
    )


def _claims(output: TaskRunJsonOutput) -> list[dict[str, object]]:
    raw = output.content.get("claims", [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _first_cited_claim(result: TaskRunResult, asset_name: str) -> RightsClaim:
    output = result.output
    if not isinstance(output, TaskRunJsonOutput):
        raise NoRightsHolderFound(asset_name)

    basis_by_field: dict[str, FieldBasis] = {basis.field: basis for basis in output.basis}
    for index, claim in enumerate(_claims(output)):
        basis = basis_by_field.get(f"claims.{index}")
        if basis is None:
            continue
        citations = basis.citations
        if not citations:
            continue
        return RightsClaim(
            holder=str(claim["holder"]),
            contact=str(claim["contact"]),
            litigation_posture=str(claim["litigation_posture"]),
            confidence=_confidence_from(basis.confidence),
            citations=_domain_citations(citations),
        )
    raise NoRightsHolderFound(asset_name)


def _domain_citations(citations: list[ParallelCitation]) -> tuple[Citation, ...]:
    return tuple(
        Citation(uri=c.url, title=c.title or "", snippet=(c.excerpts or [""])[0]) for c in citations
    )


def _confidence_from(value: str | None) -> Confidence:
    """Maps Parallel's free-form confidence string to `Confidence` (CP-016).

    `FieldBasis.confidence` is typed `Optional[str]` by the Parallel SDK, so
    any string can arrive. One nobody recognizes maps to `Confidence.LOW`,
    which under D9 flags the item for review rather than trusting it blind.
    """
    if value is None:
        return Confidence.LOW
    try:
        return Confidence(value.upper())
    except ValueError:
        return Confidence.LOW
