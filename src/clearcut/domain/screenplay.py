"""Structured screenplay invariants and immutable draft/revision references."""

import json
from dataclasses import dataclass
from typing import Any

MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
KINDS = frozenset(
    {"scene-heading", "action", "character", "dialogue", "parenthetical", "transition"}
)


class InvalidScreenplay(ValueError):
    """The document does not satisfy the stable screenplay schema."""


class DraftConflict(Exception):
    def __init__(self, current_version: int) -> None:
        super().__init__("a newer draft has been saved")
        self.current_version = current_version


@dataclass(frozen=True)
class ContentReference:
    uri: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class Draft:
    project_id: str
    version: int
    content: ContentReference | None
    updated_by: str
    updated_at: str


@dataclass(frozen=True)
class Revision:
    revision_id: str
    project_id: str
    draft_version: int
    content: ContentReference
    created_by: str
    created_at: str


def encode_document(document: dict[str, Any]) -> bytes:
    if document.get("type") != "doc" or not isinstance(document.get("content"), list):
        raise InvalidScreenplay("a screenplay document is required")
    blocks = document["content"]
    if not blocks or len(blocks) > 20000:
        raise InvalidScreenplay("a screenplay must contain 1 to 20000 blocks")
    seen_blocks: set[str] = set()
    seen_scenes: set[str] = set()
    active_scene = ""
    for block in blocks:
        if not isinstance(block, dict) or block.get("type") != "paragraph":
            raise InvalidScreenplay("screenplays contain paragraph blocks only")
        attrs = block.get("attrs", {})
        if not isinstance(attrs, dict):
            raise InvalidScreenplay("block attributes are required")
        block_id, scene_id, kind = (attrs.get(key) for key in ("blockId", "sceneId", "kind"))
        if not all(
            isinstance(value, str) and 0 < len(value) <= 128 for value in (block_id, scene_id)
        ):
            raise InvalidScreenplay("stable block and scene IDs are required")
        assert isinstance(block_id, str) and isinstance(scene_id, str)
        if block_id in seen_blocks:
            raise InvalidScreenplay("block IDs must be unique")
        seen_blocks.add(block_id)
        if not isinstance(kind, str) or kind not in KINDS:
            raise InvalidScreenplay("unknown screenplay block kind")
        if kind == "scene-heading":
            if scene_id in seen_scenes:
                raise InvalidScreenplay("scene heading IDs must be unique")
            seen_scenes.add(scene_id)
            active_scene = scene_id
        if not active_scene or scene_id != active_scene:
            raise InvalidScreenplay("each block must belong to its preceding scene heading")
        inline = block.get("content", [])
        if not isinstance(inline, list):
            raise InvalidScreenplay("invalid block content")
        for node in inline:
            if not isinstance(node, dict) or node.get("type") not in {"text", "hardBreak"}:
                raise InvalidScreenplay("only text and line breaks are accepted")
            if node["type"] == "text" and not isinstance(node.get("text"), str):
                raise InvalidScreenplay("text must be a string")
            marks = node.get("marks", [])
            if not isinstance(marks, list) or any(
                not isinstance(mark, dict) or mark.get("type") not in {"bold", "italic"}
                for mark in marks
            ):
                raise InvalidScreenplay("unsupported screenplay formatting")
    try:
        encoded = json.dumps(
            document, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise InvalidScreenplay("document is not valid JSON") from exc
    if len(encoded) > MAX_DOCUMENT_BYTES:
        raise InvalidScreenplay("screenplay exceeds the 8 MiB document limit")
    return encoded
