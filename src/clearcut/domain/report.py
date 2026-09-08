"""Fixed clearance report identity and explicitly documented counting rules."""

from dataclasses import dataclass
from typing import Any

from clearcut.domain.screenplay import ContentReference
from clearcut.domain.tracker import TrackerItem, TrackerState


class ReportConflict(Exception):
    """The requested revision or clearance epoch changed before publication."""


@dataclass(frozen=True)
class ClearanceReport:
    report_id: str
    project_id: str
    organization_id: str
    analysis_id: str
    revision_id: str
    generation_id: str
    clearance_epoch: int
    created_by: str
    created_at: str
    language: str
    snapshot: ContentReference
    pdf: ContentReference
    csv: ContentReference
    analysis_manifest: ContentReference
    counts: dict[str, int | float]
    formula_version: str = "clearance-counts-v1"
    template_version: str = "clearance-report-v1"
    production_context_sha256: str = ""
    local_research_epoch: int | None = None
    settings_version: int | None = None


def clearance_counts(items: list[TrackerItem], bindings: dict[str, Any]) -> dict[str, int | float]:
    """All retained items form the denominator; review flags override state."""
    total = len(items)
    review = sum(item.needs_review for item in items)
    cleared = sum(item.state is TrackerState.CLEARED and not item.needs_review for item in items)
    blocked = sum(item.state is TrackerState.BLOCKED and not item.needs_review for item in items)
    progress = sum(
        item.state is TrackerState.IN_PROGRESS and not item.needs_review for item in items
    )
    present = sum(bindings.get(item.item_id, {}).get("present") is True for item in items)
    absent = sum(bindings.get(item.item_id, {}).get("present") is False for item in items)
    return {
        "total_retained": total,
        "confirmed_cleared": cleared,
        "needs_review": review,
        "blocked": blocked,
        "in_progress": progress,
        "present": present,
        "not_detected": absent,
        "unknown_binding": total - present - absent,
        "confirmed_cleared_percent": round(100 * cleared / total, 1) if total else 0.0,
    }
