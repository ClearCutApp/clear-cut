from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Any

import pytest
from flask import Flask

from clearcut.adapters.demo.drafts import MemoryDraftStore, MemoryScreenplayContent
from clearcut.adapters.http.drafts import create_drafts_blueprint
from clearcut.application.screenplay_drafts import save_draft
from clearcut.domain.screenplay import DraftConflict


def document(text: str = "First version") -> dict[str, Any]:
    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "attrs": {"blockId": "block1", "sceneId": "scene1", "kind": "scene-heading"},
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(create_drafts_blueprint(MemoryDraftStore(), MemoryScreenplayContent()))
    return app.test_client()


def test_save_conflict_keeps_winner_and_revision_immutable(client):
    root = "/api/projects/project1"
    assert client.get(root + "/draft").json["version"] == 0
    assert (
        client.put(
            root + "/draft", json={"expected_version": 0, "document": document()}
        ).status_code
        == 200
    )
    frozen = client.post(root + "/revisions", json={"expected_version": 1})
    assert frozen.status_code == 201
    revision_id = frozen.json["revision_id"]
    assert client.post(root + "/revisions", json={"expected_version": 1}).json == frozen.json
    response = client.put(
        root + "/draft", json={"expected_version": 0, "document": document("Losing writer")}
    )
    assert response.status_code == 409
    assert response.json["current_version"] == 1
    assert client.get(root + "/draft").json["document"] == document()
    assert (
        client.put(
            root + "/draft", json={"expected_version": 1, "document": document("Next version")}
        ).status_code
        == 200
    )
    assert client.get(root + "/revisions/" + revision_id).json["document"] == document()
    assert client.get("/api/projects/other/revisions/" + revision_id).status_code == 404
    assert client.get(root + "/revisions").json["revisions"][0]["sha256"] == frozen.json["sha256"]
    assert "uri" not in str(frozen.json)


@pytest.mark.parametrize("version", [True, -1, "0", None])
def test_invalid_expected_version_is_rejected(client, version):
    assert (
        client.put(
            "/api/projects/p/draft", json={"expected_version": version, "document": document()}
        ).status_code
        == 400
    )


def test_duplicate_pasted_block_rejected(client):
    value = document()
    value["content"].append(deepcopy(value["content"][0]))
    assert (
        client.put(
            "/api/projects/p/draft", json={"expected_version": 0, "document": value}
        ).status_code
        == 400
    )


def test_concurrent_saves_have_exactly_one_winner():
    store, content = MemoryDraftStore(), MemoryScreenplayContent()

    def attempt(index):
        try:
            return save_draft(
                store, content, "o", "p", str(index), 0, document(str(index)), "writer", "now"
            ).version
        except DraftConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [1, 2]))
    assert sorted(results, key=str) == [1, "conflict"]
    current = store.get_draft("p")
    assert current is not None and current.version == 1
