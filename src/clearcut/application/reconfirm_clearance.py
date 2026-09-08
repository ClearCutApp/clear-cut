"""Human confirmation of applicability to one committed screenplay revision."""

import json

from clearcut.application.durable_ports import AnalysisArtifacts, ClearanceSnapshots
from clearcut.application.tracker_mutations import ClearanceConfirmation
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.tracker import InvalidClearance, TrackerConflict, TrackerItem


class ReconfirmClearance:
    def __init__(
        self,
        snapshots: ClearanceSnapshots,
        artifacts: AnalysisArtifacts,
        confirmations: ClearanceConfirmation,
    ) -> None:
        self.snapshots, self.artifacts, self.confirmations = snapshots, artifacts, confirmations

    def execute(
        self,
        project_id: str,
        item_id: str,
        expected_version: int,
        revision_id: str,
        actor: str,
        at: str,
    ) -> TrackerItem:
        baseline, items = self.snapshots.snapshot(project_id)
        item = next((item for item in items if item.item_id == item_id), None)
        if item is None:
            raise RecordNotFound("clearance not found")
        if item.version != expected_version:
            raise TrackerConflict(item.version)
        if not baseline.generation_id or baseline.manifest is None:
            raise InvalidClearance("analyze a saved revision before confirming applicability")
        manifest = self.artifacts.get(baseline.manifest)
        analyzed_context = json.loads(manifest.get("production_context_json", "{}"))
        analyzed_context.pop("analysis_jurisdiction", None)
        if analyzed_context != json.loads(baseline.production_context_json):
            raise InvalidClearance(
                "production locations changed; analyze the current context first"
            )
        binding = manifest.get("clearance_bindings", {}).get(item_id, {})
        if (
            manifest.get("project_id") != project_id
            or manifest.get("revision_id") != revision_id
            or binding.get("revision_id") != revision_id
            or binding.get("present") is not True
            or not binding.get("signature")
        ):
            raise InvalidClearance("confirm only an item detected in the current analyzed revision")
        updated = item.reconfirmed(at)
        self.confirmations.compare_reconfirm(
            updated,
            expected_version,
            actor,
            baseline.generation_id,
            revision_id,
            baseline.production_context_json,
        )
        return updated
