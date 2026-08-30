"""Confidence-to-risk mapping (docs/plan/sdd.md Section 4.1 step 5, D9).

One pure function: how a `RightsResearch` confidence resolves a finding's
risk level and whether its tracker item needs a human's review. Split out of
`AnalyzeScript` because a module that both orchestrates the pipeline and
decides risk level is two modules (AGENT.md Section 3, SRP).
"""

from dataclasses import dataclass

from clearcut.application.ports import Confidence, RightsClaim
from clearcut.domain.finding import Finding, RiskLevel


@dataclass(frozen=True)
class RiskDecision:
    """A finding's resolved risk level and its tracker item's review flag."""

    risk_level: RiskLevel
    needs_review: bool


def resolve_risk(finding: Finding, claim: RightsClaim) -> RiskDecision:
    """Map `claim.confidence` onto `finding.risk_level` (D9).

    HIGH confidence changes nothing. MEDIUM raises the risk one step through
    `RiskLevel.raised()`, which ceils at CRITICAL. LOW leaves the risk level
    alone and flags the tracker item `needs_review` instead, since `Finding`
    has no field of its own for "unverified" (D9).
    """
    if claim.confidence is Confidence.MEDIUM:
        return RiskDecision(risk_level=finding.risk_level.raised(), needs_review=False)
    if claim.confidence is Confidence.LOW:
        return RiskDecision(risk_level=finding.risk_level, needs_review=True)
    return RiskDecision(risk_level=finding.risk_level, needs_review=False)
