"""Rebase analysis-owned fields while retaining the current human decisions."""

from dataclasses import replace
from typing import Any

from clearcut.application.analysis_documents import digest, read_finding
from clearcut.application.analyze_script import AnalysisReport
from clearcut.domain.finding import Finding
from clearcut.domain.tracker import TrackerItem


def asset_key(finding: Finding) -> str:
    return digest(
        [
            finding.category.value,
            finding.ner_label.value if finding.ner_label else None,
            " ".join(finding.raw_text.casefold().split()),
        ]
    )


def reconcile_analysis(
    report: AnalysisReport,
    current_items: list[TrackerItem],
    previous_manifest: dict[str, Any] | None,
    anchors: list[dict[str, Any]],
    revision_id: str,
    production_context: str,
    at: str,
) -> tuple[list[Finding], list[TrackerItem], dict[str, Any]]:
    previous_manifest = previous_manifest or {}
    old_bindings = previous_manifest.get("clearance_bindings", {})
    old_findings = {
        value["finding_id"]: read_finding(value) for value in previous_manifest.get("findings", [])
    }
    current = {item.item_id: item for item in current_items}
    matching = {
        binding["asset_key"]: item_id
        for item_id, binding in old_bindings.items()
        if item_id in current and binding.get("asset_key")
    }
    scenes = {int(anchor["scene_number"]): anchor for anchor in anchors}
    used = set(current)
    findings: list[Finding] = []
    items: list[TrackerItem] = []
    bindings: dict[str, Any] = {}
    sequence = 0

    def new_id() -> str:
        nonlocal sequence
        while True:
            sequence += 1
            candidate = f"EVT-{sequence:03d}"
            if candidate not in used:
                used.add(candidate)
                return candidate

    for finding, generated in zip(report.findings, report.tracker_items, strict=True):
        key = asset_key(finding)
        item_id = matching.get(key) or new_id()
        old = current.get(item_id)
        appearances = [scenes[number] for number in generated.scene_numbers if number in scenes]
        if len(appearances) != len(generated.scene_numbers):
            raise ValueError("finding references a scene outside its immutable revision")
        signature = digest(
            {
                "asset": key,
                "context": production_context,
                "scenes": sorted(
                    [[scene["scene_id"], scene["content_digest"]] for scene in appearances]
                ),
                "required_document": generated.required_document,
            }
        )
        binding = {
            "asset_key": key,
            "signature": signature,
            "revision_id": revision_id,
            "present": True,
            "scene_ids": [scene["scene_id"] for scene in appearances],
        }
        resolved = replace(finding, finding_id=item_id)
        if old:
            applicable = old_bindings.get(item_id, {}).get("signature") == signature
            updated = replace(
                old,
                finding_id=item_id,
                scene_numbers=generated.scene_numbers,
                required_document=generated.required_document,
                contact=generated.contact,
                litigation_posture=generated.litigation_posture,
                rights_holder_citations=generated.rights_holder_citations,
                needs_review=old.needs_review or generated.needs_review or not applicable,
            )
            if updated != old or old_bindings.get(item_id) != binding:
                updated = replace(updated, version=old.version + 1, updated_at=at)
        else:
            updated = replace(generated, item_id=item_id, finding_id=item_id)
        findings.append(resolved)
        items.append(updated)
        bindings[item_id] = binding

    # Disappearing assets remain visible for an explicit human review. Their
    # original finding stays bound to its original revision, never re-anchored.
    for item_id, old in current.items():
        if item_id in bindings:
            continue
        binding = {**old_bindings.get(item_id, {}), "present": False}
        updated = old
        if not old.needs_review or old_bindings.get(item_id) != binding:
            updated = replace(old, needs_review=True, version=old.version + 1, updated_at=at)
        items.append(updated)
        bindings[item_id] = binding
        if item_id in old_findings:
            findings.append(old_findings[item_id])
    return findings, items, bindings
