"""Lossless JSON encodings for immutable analysis artifacts, outside HTTP shapes."""

import hashlib
import json
from dataclasses import asdict
from typing import Any

from clearcut.domain.durable_analysis import AnalysisRequest, DurableJob
from clearcut.domain.finding import Category, Citation, Finding, NerLabel, RiskLevel
from clearcut.domain.screenplay import ContentReference
from clearcut.domain.script import Scene, Script
from clearcut.domain.tracker import TrackerItem, TrackerState


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def scene_data(scene: Scene) -> dict[str, Any]:
    value = asdict(scene)
    value.pop("content_hash")
    return value


def script_data(script: Script) -> dict[str, Any]:
    return {**asdict(script), "scenes": [scene_data(scene) for scene in script.scenes]}


def read_script(value: dict[str, Any]) -> Script:
    return Script(**{**value, "scenes": [Scene(**scene) for scene in value["scenes"]]})


def finding_data(finding: Finding) -> dict[str, Any]:
    return {
        **asdict(finding),
        "category": finding.category.value,
        "ner_label": finding.ner_label.value if finding.ner_label else None,
        "risk_level": finding.risk_level.value,
    }


def read_finding(value: dict[str, Any]) -> Finding:
    return Finding(
        **{
            **value,
            "category": Category(value["category"]),
            "ner_label": NerLabel(value["ner_label"]) if value.get("ner_label") else None,
            "risk_level": RiskLevel(value["risk_level"]),
            "citations": tuple(Citation(**citation) for citation in value.get("citations", [])),
        }
    )


def tracker_data(item: TrackerItem) -> dict[str, Any]:
    return {
        **asdict(item),
        "state": item.state.value,
        "scene_numbers": list(item.scene_numbers),
        "evidence_file_ids": list(item.evidence_file_ids),
        "rights_holder_citations": [asdict(citation) for citation in item.rights_holder_citations],
    }


def read_tracker(value: dict[str, Any]) -> TrackerItem:
    return TrackerItem(
        **{
            **value,
            "state": TrackerState(value["state"]),
            "scene_numbers": tuple(value["scene_numbers"]),
            "evidence_file_ids": tuple(value.get("evidence_file_ids", [])),
            "rights_holder_citations": tuple(
                Citation(**citation) for citation in value.get("rights_holder_citations", [])
            ),
        }
    )


def read_job(data: dict[str, Any]) -> DurableJob:
    request = dict(data["request"])
    request["revision_content"] = ContentReference(**request["revision_content"])
    if request.get("baseline_manifest"):
        request["baseline_manifest"] = ContentReference(**request["baseline_manifest"])
    fields = {key: value for key, value in data.items() if key in DurableJob.__dataclass_fields__}
    fields["request"] = AnalysisRequest(**request)
    if fields.get("result"):
        fields["result"] = ContentReference(**fields["result"])
    return DurableJob(**fields)
