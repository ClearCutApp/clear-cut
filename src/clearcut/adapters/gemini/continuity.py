"""Gemini adapter for `ContinuityCheck` (docs/plan/sdd.md Section 4.1 step 5,
docs/plan/agentic-workflow.md Section 2.2, ADR 0002, D11).

One gemini-3.1-flash-lite call per scene, comparing it against the bible
facts `LoreStore` retrieved. `response_schema` is pinned to the check-result
shape so the model's JSON always parses. Temperature stays unset (the API
default): ADR 0002 records that lowering it degrades Gemini 3 output. An
empty `facts` list short-circuits before any client call — a project with no
indexed bible must not spend a Gemini call per scene.
"""

import json
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from google.genai import types

from clearcut.domain.bible import BibleFact
from clearcut.domain.finding import Category, Finding, RiskLevel
from clearcut.domain.script import Scene

_VALID_CATEGORIES = frozenset({Category.CONTINUITY, Category.POLICY})

_SYSTEM_INSTRUCTION = (
    "You are a script-continuity and policy auditor. Compare the scene against "
    "the project bible facts provided. A LORE fact states established story "
    "history; a POLICY fact states a production rule such as an age rating or "
    "brand restriction. If the scene contradicts exactly one fact, respond with "
    "that fact's fact_id in contradicts, category set to CONTINUITY for a LORE "
    "contradiction or POLICY for a POLICY violation, the exact raw_text span "
    "that contradicts it, a risk_level (LOW, MEDIUM, HIGH, or CRITICAL), and "
    "the required_document needed to resolve it. Judge the scene only against "
    "the facts given. If the scene contradicts nothing, respond with "
    "contradicts set to null and leave the other fields null."
)

_CHECK_RESULT_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "contradicts": types.Schema(type=types.Type.STRING, nullable=True),
        "category": types.Schema(
            type=types.Type.STRING,
            enum=[category.value for category in _VALID_CATEGORIES],
            nullable=True,
        ),
        "raw_text": types.Schema(type=types.Type.STRING, nullable=True),
        "risk_level": types.Schema(
            type=types.Type.STRING, enum=[level.value for level in RiskLevel], nullable=True
        ),
        "required_document": types.Schema(type=types.Type.STRING, nullable=True),
    },
    required=["contradicts"],
)


class ContinuityCheckFailed(Exception):
    """Raised when a Gemini response names a category outside CONTINUITY/POLICY."""

    def __init__(self, category: object) -> None:
        super().__init__(f"unrecognized category: {category!r}")
        self.category = category


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


def _scene_text(scene: Scene) -> str:
    return f"SCENE {scene.number} (page {scene.page_start}-{scene.page_end}): {scene.text}"


def _fact_text(fact: BibleFact) -> str:
    return f"FACT {fact.fact_id} ({fact.kind}, source {fact.source}): {fact.text}"


def _category(value: object) -> Category:
    try:
        category = Category(str(value))
    except ValueError:
        raise ContinuityCheckFailed(value) from None
    if category not in _VALID_CATEGORIES:
        raise ContinuityCheckFailed(value)
    return category


@dataclass(frozen=True)
class GeminiContinuityCheck:
    """Implements `ContinuityCheck` over one gemini-3.1-flash-lite call per scene."""

    client: _GeminiClient
    model: str

    def check(self, scene: Scene, facts: list[BibleFact]) -> Finding | None:
        if not facts:
            return None
        config = types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=_CHECK_RESULT_SCHEMA,
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=[_scene_text(scene)] + [_fact_text(fact) for fact in facts],
            config=config,
        )
        item: dict[str, Any] = json.loads(response.text or "{}")
        contradicts = item.get("contradicts")
        if not contradicts:
            return None
        return self._to_finding(scene, str(contradicts), item)

    def _to_finding(self, scene: Scene, contradicts: str, item: dict[str, Any]) -> Finding:
        return Finding(
            finding_id=str(uuid.uuid4()),
            scene_number=scene.number,
            page=scene.page_start,
            raw_text=str(item["raw_text"]),
            category=_category(item["category"]),
            ner_label=None,
            risk_level=RiskLevel(str(item["risk_level"])),
            required_document=str(item["required_document"]),
            contradicts=contradicts,
        )
