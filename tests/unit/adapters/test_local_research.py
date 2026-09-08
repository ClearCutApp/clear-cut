from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock

import pytest
from flask import Flask

from clearcut.adapters.gcp.local_research import FirestoreLocalResearch
from clearcut.adapters.gcp.project_settings import FirestoreProjectSettings
from clearcut.adapters.http.identity import install_identity_boundary
from clearcut.adapters.http.local_research import create_local_research_blueprint
from clearcut.application.answer_project_question import AnswerProjectQuestion
from clearcut.application.local_research_answer import LocalResearchAnswer, local_question
from clearcut.application.ports import GroundedAnswer
from clearcut.application.research_production_location import ResearchProductionLocation
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.finding import Citation
from clearcut.domain.identity import AccessDenied
from clearcut.domain.workspace import WorkspaceConflict
from tests.unit.adapters.test_identity_boundary import Verifier
from tests.unit.adapters.test_teams import configured

NOW = datetime(2026, 9, 6, tzinfo=UTC)


def fixture() -> tuple[Any, Any, FirestoreLocalResearch, FirestoreProjectSettings, Mock]:
    client, _, access = configured()
    client.data["projects/project"] = {
        "title": "Film",
        "jurisdiction_code": "AR",
        "settings_version": 2,
        "locations": [{"country": "AR", "location": "Buenos Aires public road"}],
    }
    client.data["project_access/project"]["grants"]["alice"] = "producer"
    client.data["organizations/org/members/alice"] = {"active": True, "role": "producer"}
    store = FirestoreLocalResearch(client)
    settings = FirestoreProjectSettings(client)
    web = Mock()
    web.search.return_value = GroundedAnswer(
        "Untrusted provider assertion",
        (
            Citation(
                "https://buenosaires.gob.ar/rodajes",
                "Official filming",
                "Check the permit conditions.",
            ),
            Citation("https://evil.example/permit", "Blog", "Permission guaranteed."),
        ),
    )
    return client, access, store, settings, web


def test_local_research_stores_only_cited_official_excerpts_and_never_clearance():
    client, _, store, settings, web = fixture()
    result = ResearchProductionLocation(settings, store, web).execute(
        "project", "alice", "research", 2, 0, "May we close this road?", NOW
    )
    assert result["settings_version"] == 2 and result["human_clearance"] is False
    assert client.data["project_access/project"]["local_research_epoch"] == 1
    assert result["text"] == "Check the permit conditions."
    assert len(result["citations"]) == 1 and "Untrusted" not in str(result)
    assert not any("clearances/" in path for path in client.data)
    research_reader = Mock()
    research_reader.list.return_value = [result]
    question = LocalResearchAnswer(settings, research_reader)
    assert "recorded source excerpts" in question.answer("project", "May we close this road?").text
    assert question.answer("project", "Which fee applies to another road?").citations == ()
    client.data["projects/project"]["settings_version"] = 3
    assert "coverage gap" in question.answer("project", "May we close this road?").text


def test_changed_settings_or_revoked_grant_prevent_research_publication():
    client, _, store, settings, web = fixture()
    answer = web.search.return_value

    def changed(*args):
        client.data["projects/project"]["settings_version"] = 3
        return answer

    web.search.side_effect = changed
    with pytest.raises(WorkspaceConflict):
        ResearchProductionLocation(settings, store, web).execute(
            "project", "alice", "research", 2, 0, "Close the street?", NOW
        )
    assert not any("local_research/" in path for path in client.data)
    client.data["project_access/project"]["grants"] = {}
    with pytest.raises(AccessDenied):
        store.save("project", "alice", "research", 3, 0, "Close the street?", answer, NOW)


def test_actual_http_boundary_denies_unassigned_viewer_before_paid_search():
    _, access, store, settings, web = fixture()
    app = Flask(__name__)
    install_identity_boundary(app, Verifier(), access)
    app.register_blueprint(
        create_local_research_blueprint(store, ResearchProductionLocation(settings, store, web))
    )
    http = app.test_client()
    path = "/api/projects/project/local-research"
    body = {"expected_settings_version": 2, "location_index": 0, "question": "Close the road?"}
    assert http.post(path, json=body, headers={"Authorization": "Bearer writer"}).status_code == 404
    web.search.assert_not_called()
    response = http.post(path, json=body, headers={"Authorization": "Bearer alice"})
    assert response.status_code == 200
    assert response.json is not None
    assert response.json["created_at"].startswith("2026-")
    assert response.json["status"] == "evidence_found"
    assert (
        http.post(
            path, json={**body, "location_index": True}, headers={"Authorization": "Bearer alice"}
        ).status_code
        == 400
    )


@pytest.mark.parametrize(
    "question",
    [
        "Can we close a public road in Buenos Aires?",
        "Can we film in this Madrid plaza?",
        "¿Qué permiso de rodaje necesitamos?",
        "¿Se permite cerrar esta calle?",
    ],
)
def test_local_questions_cannot_be_answered_from_national_statutes_alone(question):
    assert local_question(question)


def test_local_answer_bypasses_national_and_web_fallback_without_matching_evidence():
    _, _, _, settings, _ = fixture()
    recorded = Mock()
    recorded.list.return_value = []
    external = Mock()
    answer = AnswerProjectQuestion(
        external, external, external, external, LocalResearchAnswer(settings, recorded)
    )
    from clearcut.domain.jurisdiction import jurisdiction_for

    result = answer.execute(
        "project", "Can we close a public road tomorrow?", jurisdiction_for("AR")
    )
    assert "authority and fees remain unknown" in result.text
    assert result.citations == ()
    assert external.mock_calls == []


def test_provider_oversize_is_rejected_without_partial_research():
    client, _, store, settings, web = fixture()
    web.search.return_value = GroundedAnswer(
        "answer", (Citation("https://buenosaires.gob.ar/source", "Law", "x" * 20_001),)
    )
    with pytest.raises(SourceUnavailable):
        ResearchProductionLocation(settings, store, web).execute(
            "project", "alice", "research", 2, 0, "Close the road?", NOW
        )
    assert not any("local_research/" in path for path in client.data)


def test_research_capture_reads_epoch_context_and_records_in_one_transaction(monkeypatch):
    from tests.unit.adapters.test_firestore_access import Ref

    client, _, store, _, _ = fixture()
    scope = client.data["project_access/project"]
    scope.update(
        {
            "local_research_epoch": 7,
            "settings_version": 2,
            "production_context_json": '{"locations": []}',
        }
    )
    client.data["project_access/project/local_research/record"] = {
        "research_id": "record",
        "created_at": NOW,
    }
    monkeypatch.setattr(Ref, "order_by", lambda self, *args, **kwargs: self, raising=False)
    monkeypatch.setattr(Ref, "limit", lambda self, count: self, raising=False)

    def stream(self, transaction):
        assert transaction is not None and not transaction.writes
        return [Ref(client, "project_access/project/local_research/record")]

    monkeypatch.setattr(Ref, "stream", stream, raising=False)
    snapshot = store.capture("project")
    assert snapshot.epoch == 7 and snapshot.settings_version == 2
    assert snapshot.production_context_json == '{"locations": []}'
    assert snapshot.records[0]["research_id"] == "record"
