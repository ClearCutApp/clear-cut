"""Stable IDs make scene and block identity survive text editing."""

import copy
from typing import Any

import pytest

from clearcut.domain.screenplay import InvalidScreenplay, encode_document


def document() -> dict[str, Any]:
    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "attrs": {"blockId": "block-one", "sceneId": "scene-one", "kind": "scene-heading"},
                "content": [{"type": "text", "text": "INT. ROOM - DAY"}],
            }
        ],
    }


def test_document_preserves_stable_ids_after_text_changes():
    original = document()
    changed = copy.deepcopy(original)
    changed["content"][0]["content"][0]["text"] = "EXT. ROOM - NIGHT"
    assert b"block-one" in encode_document(changed)
    assert b"scene-one" in encode_document(changed)
    assert encode_document(original) != encode_document(changed)


def test_duplicate_block_ids_are_rejected():
    value = document()
    value["content"].append(copy.deepcopy(value["content"][0]))
    with pytest.raises(InvalidScreenplay, match="block IDs"):
        encode_document(value)


def test_a_block_cannot_claim_another_scenes_identity():
    value = document()
    value["content"].append(
        {
            "type": "paragraph",
            "attrs": {"blockId": "block-two", "sceneId": "another-scene", "kind": "action"},
        }
    )
    with pytest.raises(InvalidScreenplay, match="preceding scene"):
        encode_document(value)


def test_executable_or_unsupported_content_is_rejected():
    value = document()
    value["content"][0]["content"] = [{"type": "html", "text": "<script>bad()</script>"}]
    with pytest.raises(InvalidScreenplay):
        encode_document(value)
