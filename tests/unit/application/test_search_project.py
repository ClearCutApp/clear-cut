"""Search is literal, private, revision-bound and explicit about coverage."""

import json
from dataclasses import replace
from unittest.mock import Mock

import pytest
from flask import Flask

from clearcut.adapters.http.identity import install_identity_boundary
from clearcut.adapters.http.search import create_search_blueprint
from clearcut.application.search_project import SearchProject
from clearcut.domain.document import ProjectDocument
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.screenplay import ContentReference, Revision
from clearcut.domain.workspace import InvalidWorkspace, WorkspaceConflict
from tests.unit.adapters.test_clearance_transactions import item
from tests.unit.adapters.test_identity_boundary import Access, Verifier


def setup() -> tuple[SearchProject, Mock, Mock, Mock, Mock, Mock]:
    drafts, content, tracker, documents, research = [Mock() for _ in range(5)]
    drafts.revisions.return_value = [
        Revision("revision", "one", 3, ContentReference("uri", "hash", 10), "writer", "now")
    ]
    content.get.return_value = json.dumps(
        {
            "content": [
                {
                    "attrs": {"kind": "scene-heading", "blockId": "heading", "sceneId": "scene"},
                    "content": [{"text": "EXT. CALLE – DÍA"}],
                },
                {
                    "attrs": {"kind": "dialogue", "blockId": "dialogue", "sceneId": "scene"},
                    "content": [{"text": "Música en Bogotá"}],
                },
            ]
        }
    ).encode()
    tracker.execute.return_value = [replace(item(), note="Música rights")]
    documents.list.return_value = []
    research.list.return_value = []
    return (
        SearchProject(drafts, content, tracker, documents, research),
        drafts,
        content,
        tracker,
        documents,
        research,
    )


def test_search_matches_accents_without_regex_and_keeps_exact_revision_scene():
    search, drafts, _, tracker, documents, research = setup()
    page = search.execute("one", "musica")
    assert page["total"] == 2
    result = next(value for value in page["results"] if value["kind"] == "script")
    assert result["revision_id"] == "revision" and result["scene_id"] == "scene"
    assert result["excerpt"] == "Música en Bogotá"
    assert search.execute("one", ".*")["total"] == 0
    assert page["coverage"] == [
        "latest_saved_revision",
        "current_clearances",
        "document_names",
        "latest_50_local_research",
    ]
    drafts.revisions.assert_called_with("one")
    tracker.execute.assert_called_with("one")
    documents.list.assert_called_with("one", None)
    research.list.assert_called_with("one")


def test_large_result_pages_do_not_truncate_and_reject_changed_query_or_source():
    search, _, _, tracker, _, _ = setup()
    tracker.execute.return_value = [
        replace(item(), item_id=f"asset-{n:03}", note="matching") for n in range(175)
    ]
    first = search.execute("one", "matching")
    assert first["total"] == 175 and len(first["results"]) == 50
    ids = {value["id"] for value in first["results"]}
    cursor = first["next_cursor"]
    while cursor:
        page = search.execute("one", "matching", cursor)
        ids.update(value["id"] for value in page["results"])
        cursor = page["next_cursor"]
    assert len(ids) == 175
    with pytest.raises(WorkspaceConflict):
        search.execute("one", "different", first["next_cursor"])
    tracker.execute.return_value[0] = replace(tracker.execute.return_value[0], version=2)
    with pytest.raises(WorkspaceConflict):
        search.execute("one", "matching", first["next_cursor"])


def test_document_search_continues_past_first_metadata_page_and_never_fetches_bytes():
    search, _, _, _, documents, _ = setup()
    values = [
        ProjectDocument(
            str(n),
            "org",
            "one",
            f"evidence-{n}.pdf",
            "application/pdf",
            20,
            "hash",
            "uri",
            "evidence",
            "producer",
            "now",
        )
        for n in range(51)
    ]
    documents.list.side_effect = lambda project, before: (
        values[:50] if before is None else values[50:]
    )
    result = search.execute("one", "evidence-50")
    assert result["total"] == 1 and result["results"][0]["id"] == "50"
    assert documents.list.call_args_list[-1].args == ("one", "49")
    documents.get.assert_not_called()


def test_unavailable_source_never_returns_a_misleading_partial_search():
    search, _, _, _, _, research = setup()
    research.list.side_effect = SourceUnavailable("unavailable")
    with pytest.raises(SourceUnavailable):
        search.execute("one", "musica")
    for query in ("x", "x" * 201, "  "):
        with pytest.raises(InvalidWorkspace):
            search.execute("one", query)


def test_http_search_requires_project_read_permission_and_keeps_queries_out_of_urls():
    search = Mock()
    search.execute.return_value = {"results": [], "total": 0}
    app = Flask(__name__)
    install_identity_boundary(app, Verifier(), Access())
    app.register_blueprint(create_search_blueprint(search))
    http = app.test_client()
    path = "/api/projects/one/search"
    assert (
        http.post(
            path, json={"query": "private phrase"}, headers={"Authorization": "Bearer bob"}
        ).status_code
        == 404
    )
    search.execute.assert_not_called()
    result = http.post(
        path, json={"query": "private phrase"}, headers={"Authorization": "Bearer viewer"}
    )
    assert result.status_code == 200 and result.headers["Cache-Control"] == "no-store"
    search.execute.assert_called_once_with("one", "private phrase", None)
    assert (
        http.post(
            path,
            json={"query": "private", "cursor": "x" * 513},
            headers={"Authorization": "Bearer viewer"},
        ).status_code
        == 400
    )


def test_long_field_excerpt_contains_the_actual_accent_folded_match():
    search, _, _, tracker, _, _ = setup()
    tracker.execute.return_value = [
        replace(item(), note="x" * 1000 + " Bogotá música " + "y" * 1000)
    ]
    result = search.execute("one", "bogota musica")
    assert "Bogotá música" in result["results"][0]["excerpt"]
    assert len(result["results"][0]["excerpt"]) <= 502
