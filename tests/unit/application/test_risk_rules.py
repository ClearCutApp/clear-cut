"""Tests for the confidence-to-risk rule (CP-021, docs/plan/sdd.md Section 4.1
step 5, D9).
"""

from typing import Any

import pytest

from clearcut.application.ports import Confidence, RightsClaim
from clearcut.application.risk_rules import RiskDecision, resolve_risk
from clearcut.domain.finding import Category, Finding, NerLabel, RiskLevel


def _finding(**overrides: Any) -> Finding:
    fields: dict[str, Any] = dict(
        finding_id="EVT-001",
        scene_number=4,
        page=12,
        raw_text="a bottle of Quilmes",
        category=Category.INDUSTRIAL_PROPERTY,
        ner_label=NerLabel.BRAND,
        risk_level=RiskLevel.MEDIUM,
        required_document="Trademark Clearance Form",
    )
    fields.update(overrides)
    return Finding(**fields)


def _claim(confidence: Confidence) -> RightsClaim:
    return RightsClaim(
        holder="Quilmes S.A.",
        contact="legal@quilmes.example",
        litigation_posture="no known disputes",
        confidence=confidence,
    )


def test_high_confidence_leaves_risk_and_needs_review_unchanged():
    finding = _finding(risk_level=RiskLevel.MEDIUM)
    decision = resolve_risk(finding, _claim(Confidence.HIGH))
    assert decision == RiskDecision(risk_level=RiskLevel.MEDIUM, needs_review=False)


def test_medium_confidence_raises_risk_one_step():
    finding = _finding(risk_level=RiskLevel.LOW)
    decision = resolve_risk(finding, _claim(Confidence.MEDIUM))
    assert decision == RiskDecision(risk_level=RiskLevel.MEDIUM, needs_review=False)


def test_low_confidence_leaves_risk_unchanged_and_flags_needs_review():
    finding = _finding(risk_level=RiskLevel.HIGH)
    decision = resolve_risk(finding, _claim(Confidence.LOW))
    assert decision == RiskDecision(risk_level=RiskLevel.HIGH, needs_review=True)


def test_critical_finding_at_medium_confidence_stays_critical():
    finding = _finding(risk_level=RiskLevel.CRITICAL)
    decision = resolve_risk(finding, _claim(Confidence.MEDIUM))
    assert decision == RiskDecision(risk_level=RiskLevel.CRITICAL, needs_review=False)


_CONFIDENCE_RISK_TABLE = [
    (RiskLevel.LOW, Confidence.HIGH, RiskLevel.LOW, False),
    (RiskLevel.LOW, Confidence.MEDIUM, RiskLevel.MEDIUM, False),
    (RiskLevel.LOW, Confidence.LOW, RiskLevel.LOW, True),
    (RiskLevel.MEDIUM, Confidence.HIGH, RiskLevel.MEDIUM, False),
    (RiskLevel.MEDIUM, Confidence.MEDIUM, RiskLevel.HIGH, False),
    (RiskLevel.MEDIUM, Confidence.LOW, RiskLevel.MEDIUM, True),
    (RiskLevel.HIGH, Confidence.HIGH, RiskLevel.HIGH, False),
    (RiskLevel.HIGH, Confidence.MEDIUM, RiskLevel.CRITICAL, False),
    (RiskLevel.HIGH, Confidence.LOW, RiskLevel.HIGH, True),
    (RiskLevel.CRITICAL, Confidence.HIGH, RiskLevel.CRITICAL, False),
    (RiskLevel.CRITICAL, Confidence.MEDIUM, RiskLevel.CRITICAL, False),
    (RiskLevel.CRITICAL, Confidence.LOW, RiskLevel.CRITICAL, True),
]


@pytest.mark.parametrize(
    "starting_risk,confidence,expected_risk,expected_needs_review",
    _CONFIDENCE_RISK_TABLE,
)
def test_confidence_to_risk_table(
    starting_risk: RiskLevel,
    confidence: Confidence,
    expected_risk: RiskLevel,
    expected_needs_review: bool,
):
    finding = _finding(risk_level=starting_risk)
    decision = resolve_risk(finding, _claim(confidence))
    assert decision == RiskDecision(risk_level=expected_risk, needs_review=expected_needs_review)
