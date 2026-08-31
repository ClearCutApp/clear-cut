"""Gemini adapter for `SceneExtractor` (docs/plan/sdd.md Section 3, ADR 0002).

One gemini-3.7-flash call per batch of up to eight scenes. `response_schema`
is pinned to the finding shape so the model's JSON always parses — pinning
the schema, not `response_mime_type` alone, is what SDD Section 3 says makes
that guarantee hold. Temperature stays unset (the API default, 1.0): ADR 0002
records that lowering it degrades Gemini 3 output. `category` is always
re-derived from the returned `ner_label` through `category_for`, never read
off the model's own `category` string, so the taxonomy keeps one owner.
"""

import json
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from google.genai import types

from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.finding import Finding, NerLabel, RiskLevel
from clearcut.domain.jurisdiction import Jurisdiction
from clearcut.domain.script import Scene
from clearcut.domain.taxonomy import category_for

_BATCH_SIZE = 8

_SYSTEM_INSTRUCTION_TEMPLATE = (
    "You are a script-clearance IP extractor reviewing scenes for the {jurisdiction} "
    "jurisdiction. For each scene, find every entity that needs legal clearance: "
    "brands, existing or original music, art or literary references, film/TV clips, "
    "named talent or characters, real people, prop or costume designs, private or "
    "public locations, and special symbols. Label each finding with exactly one of "
    "these NER tags: " + ", ".join(label.value for label in NerLabel) + ". "
    "For every finding, report the scene_number it came from, the exact raw_text "
    "span, a risk_level (LOW, MEDIUM, HIGH, or CRITICAL), and the required_document "
    "needed to clear it."
)

_FINDING_ITEM_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "scene_number": types.Schema(type=types.Type.INTEGER),
        "category": types.Schema(type=types.Type.STRING),
        "ner_label": types.Schema(type=types.Type.STRING, enum=[label.value for label in NerLabel]),
        "raw_text": types.Schema(type=types.Type.STRING),
        "risk_level": types.Schema(
            type=types.Type.STRING, enum=[level.value for level in RiskLevel]
        ),
        "required_document": types.Schema(type=types.Type.STRING),
    },
    required=[
        "scene_number",
        "category",
        "ner_label",
        "raw_text",
        "risk_level",
        "required_document",
    ],
)

_FINDINGS_SCHEMA = types.Schema(type=types.Type.ARRAY, items=_FINDING_ITEM_SCHEMA)


class ExtractionFailed(SourceUnavailable):
    """Raised when a Gemini response cannot become valid `Finding`s."""

    def __init__(self, ner_label: object) -> None:
        super().__init__(f"unrecognized ner_label: {ner_label!r}")
        self.ner_label = ner_label


class _GenerateContentResponse(Protocol):
    @property
    def text(self) -> str | None: ...


class _GenerateContentModel(Protocol):
    def generate_content(
        self,
        *,
        model: str,
        contents: types.ContentListUnionDict,
        config: types.GenerateContentConfigOrDict | None = None,
    ) -> _GenerateContentResponse: ...


class _GeminiClient(Protocol):
    @property
    def models(self) -> _GenerateContentModel: ...


def _batched(scenes: list[Scene], size: int) -> list[list[Scene]]:
    return [scenes[i : i + size] for i in range(0, len(scenes), size)]


def _scene_text(scene: Scene) -> str:
    return f"SCENE {scene.number} (page {scene.page_start}-{scene.page_end}): {scene.text}"


def _ner_label(value: object) -> NerLabel:
    try:
        return NerLabel(str(value))
    except ValueError:
        raise ExtractionFailed(value) from None


@dataclass(frozen=True)
class GeminiSceneExtractor:
    """Implements `SceneExtractor` over one gemini-3.7-flash call per batch."""

    client: _GeminiClient
    model: str

    def extract(self, scenes: list[Scene], jurisdiction: Jurisdiction) -> list[Finding]:
        findings: list[Finding] = []
        for batch in _batched(scenes, _BATCH_SIZE):
            findings.extend(self._extract_batch(batch, jurisdiction))
        return findings

    def _extract_batch(self, batch: list[Scene], jurisdiction: Jurisdiction) -> list[Finding]:
        by_number = {scene.number: scene for scene in batch}
        config = types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION_TEMPLATE.format(
                jurisdiction=jurisdiction.display_name
            ),
            response_mime_type="application/json",
            response_schema=_FINDINGS_SCHEMA,
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.HIGH),
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=[_scene_text(scene) for scene in batch],
            config=config,
        )
        items: list[dict[str, Any]] = json.loads(response.text or "[]")
        return [self._to_finding(item, by_number) for item in items]

    def _to_finding(self, item: dict[str, Any], by_number: dict[int, Scene]) -> Finding:
        ner_label = _ner_label(item["ner_label"])
        scene = by_number[int(item["scene_number"])]
        return Finding(
            finding_id=str(uuid.uuid4()),
            scene_number=scene.number,
            page=scene.page_start,
            raw_text=str(item["raw_text"]),
            category=category_for(ner_label),
            ner_label=ner_label,
            risk_level=RiskLevel(str(item["risk_level"])),
            required_document=str(item["required_document"]),
        )
