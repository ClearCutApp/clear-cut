"""Stable scene/block anchors from a validated revision and its actual PDF layout."""

from typing import Any

from clearcut.application.analysis_documents import digest
from clearcut.domain.screenplay import encode_document
from clearcut.domain.script import Scene


def revision_scenes(
    document: dict[str, Any], pages: dict[str, tuple[int, int]]
) -> tuple[list[Scene], list[dict[str, Any]]]:
    encode_document(document)
    grouped: list[list[dict[str, Any]]] = []
    for block in document["content"]:
        if block["attrs"]["kind"] == "scene-heading":
            grouped.append([])
        grouped[-1].append(block)
    scenes: list[Scene] = []
    anchors: list[dict[str, Any]] = []
    for number, blocks in enumerate(grouped, 1):
        texts: list[str] = []
        block_anchors: list[dict[str, Any]] = []
        offset = 0
        for block in blocks:
            block_id = block["attrs"]["blockId"]
            page_start, page_end = pages[block_id]
            text = "".join(node.get("text", "\n") for node in block.get("content", []))
            texts.append(text)
            block_anchors.append(
                {
                    "block_id": block_id,
                    "kind": block["attrs"]["kind"],
                    "start": offset,
                    "end": offset + len(text),
                    "page_start": page_start,
                    "page_end": page_end,
                }
            )
            offset += len(text) + 1
        scene = Scene(
            number,
            texts[0],
            block_anchors[0]["page_start"],
            block_anchors[-1]["page_end"],
            "\n".join(texts),
        )
        scenes.append(scene)
        anchors.append(
            {
                "scene_number": number,
                "scene_id": blocks[0]["attrs"]["sceneId"],
                "content_digest": digest(blocks),
                "blocks": block_anchors,
            }
        )
    return scenes, anchors
