from unittest.mock import Mock

import httpx
import pytest

from clearcut.adapters.gcp.vertex_search import VertexSearchGrounding
from clearcut.adapters.gemini.continuity import GeminiContinuityCheck
from clearcut.adapters.gemini.extractor import GeminiSceneExtractor
from clearcut.domain.bible import BibleFact, FactKind
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.jurisdiction import jurisdiction_for
from clearcut.domain.script import Scene


@pytest.mark.parametrize("stage", ["extract", "continuity", "ground"])
def test_http_timeout_is_sanitized_and_translated_without_adapter_retry(stage):
    client = Mock()
    client.models.generate_content.side_effect = httpx.ReadTimeout("private provider details")
    scene = Scene(1, "EXT. STREET - DAY", 1, 1, "Private screenplay text")
    with pytest.raises(SourceUnavailable) as caught:
        if stage == "extract":
            GeminiSceneExtractor(client, "model").extract([scene], jurisdiction_for("AR"))
        elif stage == "continuity":
            GeminiContinuityCheck(client, "model").check(
                scene, [BibleFact("fact", FactKind.LORE, "Private lore", "author")]
            )
        else:
            VertexSearchGrounding(client.models, "store").ground(
                "Private question", jurisdiction_for("AR")
            )
    assert "private" not in str(caught.value).lower()
    assert client.models.generate_content.call_count == 1


def test_spanish_rights_question_uses_legal_grounding_instead_of_scene_only_evidence():
    from clearcut.application.answer_project_question import AnswerProjectQuestion
    from clearcut.application.ports import GroundedAnswer
    from clearcut.domain.finding import Citation

    lore, grounding, tracker, web, scenes = (Mock() for _ in range(5))
    lore.search.return_value = []
    citation = Citation("https://www.boe.es/law", "Law", "Relevant right")
    grounding.ground.return_value = GroundedAnswer("Cited legal answer", (citation,))
    result = AnswerProjectQuestion(lore, grounding, tracker, web, scenes=scenes).execute(
        "project", "¿Podemos mostrar el mural sin autorización?", jurisdiction_for("ES")
    )
    assert result.citations == (citation,)
    grounding.ground.assert_called_once()
    scenes.answer.assert_not_called()


def test_oversized_question_is_rejected_before_any_provider_call():
    from flask import Flask

    from clearcut.adapters.http.questions import create_questions_blueprint

    answer = Mock()
    app = Flask(__name__)
    app.register_blueprint(create_questions_blueprint(answer))
    response = app.test_client().post(
        "/api/projects/project/questions", json={"question": "x" * 4001, "jurisdiction_code": "AR"}
    )
    assert response.status_code == 400
    answer.execute.assert_not_called()
