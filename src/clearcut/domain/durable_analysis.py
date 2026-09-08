"""Durable analysis identity, immutable input and fenced execution ownership."""

from dataclasses import dataclass
from datetime import datetime

from clearcut.domain.screenplay import ContentReference


class AnalysisBusy(Exception):
    """The project already has an unfinished analysis."""


class LeaseLost(Exception):
    """This worker no longer owns the execution; it must publish nothing."""


class AnalysisCancelled(Exception):
    """Cancellation prevents any further provider call or result publication."""


class RetryAnalysis(Exception):
    """A bounded retry can resume from already persisted provider checkpoints."""


@dataclass(frozen=True)
class NewAnalysis:
    analysis_id: str
    script_id: str
    project_id: str
    organization_id: str
    actor: str
    revision_id: str
    jurisdiction_code: str
    provider_config_json: str
    created_at: datetime


@dataclass(frozen=True)
class AnalysisRequest:
    analysis_id: str
    script_id: str
    project_id: str
    organization_id: str
    actor: str
    revision_id: str
    revision_content: ContentReference
    script_version: int
    jurisdiction_code: str
    provider_config_json: str
    production_context_json: str
    baseline_generation: str
    baseline_manifest: ContentReference | None
    created_at: datetime
    revision_version: int = 0
    settings_version: int = 1


@dataclass(frozen=True)
class DurableJob:
    request: AnalysisRequest
    state: str
    stage: str
    updated_at: datetime
    attempt: int = 0
    fence: int = 0
    lease_owner: str = ""
    lease_until: datetime | None = None
    cancel_requested: bool = False
    error_code: str = ""
    result: ContentReference | None = None
    generation_id: str = ""
    available_at: datetime | None = None

    @property
    def terminal(self) -> bool:
        return self.state in {"SUCCEEDED", "FAILED", "CANCELLED"}


@dataclass(frozen=True)
class ClearanceSnapshot:
    generation_id: str
    epoch: int
    manifest: ContentReference | None
    production_context_json: str = "{}"
