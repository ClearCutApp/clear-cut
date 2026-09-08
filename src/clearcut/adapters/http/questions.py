"""Questions: grounded questions about one project's clearance state.

Answers combine project bible facts, legal citations or completed revision scene
projections. Local questions require matching recorded production research.
Missing evidence or indexing is an explicit gap; no answer changes clearance.

`question` is required and checked here, before any adapter is reached: a
blank question would otherwise spend a Vertex AI Search call and a model
round trip on nothing, and come back with an answer to a question nobody
asked.
"""

from typing import Any

from flask import Blueprint
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import errors, schemas, serializers, validators
from clearcut.application.answer_project_question import AnswerProjectQuestion
from clearcut.domain.jurisdiction import Jurisdiction

JsonDict = dict[str, Any]

TAG = "Questions"

TAG_DESCRIPTION = "Grounded questions about one project's clearance state."

SCHEMAS: JsonDict = {
    "QuestionCreate": {
        "type": "object",
        "required": ["question", "jurisdiction_code"],
        "properties": {
            "question": {"type": "string", "minLength": 1, "maxLength": 4000},
            "jurisdiction_code": {
                "type": "string",
                "description": "The corpus the answer is grounded in.",
            },
        },
        "additionalProperties": False,
    },
    "QuestionAnswer": {
        "type": "object",
        "required": ["text", "facts", "citations"],
        "properties": {
            "text": {"type": "string", "description": "The answer."},
            "facts": {
                "type": "array",
                "description": (
                    "The project bible facts the answer drew on. Empty when it drew on none."
                ),
                "items": schemas.ref("BibleFact"),
            },
            "citations": {
                "type": "array",
                "description": "Supporting legal sources or exact saved-revision scene references.",
                "items": schemas.ref("Citation"),
            },
        },
        "additionalProperties": False,
    },
}

PATHS: JsonDict = {
    "/api/projects/{project_id}/questions": {
        "parameters": [schemas.PROJECT_ID],
        "post": {
            "tags": [TAG],
            "operationId": "askProjectQuestion",
            "summary": "Ask about this project's clearance state",
            "description": (
                "Answers from authorized project facts, cited legal sources or the completed "
                "scene projection for the committed revision. Local questions require recorded "
                "production-location evidence. Missing evidence and incomplete indexing are "
                "reported explicitly; research never grants clearance."
            ),
            "requestBody": schemas.body(schemas.ref("QuestionCreate")),
            "responses": {
                "200": schemas.ok(
                    "The answer, the bible facts behind it, and its citations.",
                    schemas.json_of(schemas.ref("QuestionAnswer")),
                ),
                "400": schemas.failure(
                    "`question` is missing, blank, or whitespace only, or "
                    "`jurisdiction_code` names no supported jurisdiction."
                ),
                "404": schemas.NOT_FOUND,
                "502": schemas.failure("The grounding service or the web search could not answer."),
                "500": schemas.INTERNAL_ERROR,
            },
        },
    },
}


def create_questions_blueprint(answer_project_question: AnswerProjectQuestion) -> Blueprint:
    bp = Blueprint("clearcut_questions", __name__)

    @bp.route("/api/projects/<project_id>/questions", methods=["POST"])
    def questions_create(project_id: str) -> ResponseReturnValue:
        payload = validators.json_body()
        question = validators.require_field(payload, "question")
        if not isinstance(question, str):
            return question
        if len(question) > 4000:
            return errors.error_response(400, "question exceeds 4000 characters")
        jurisdiction = validators.resolve_jurisdiction(str(payload.get("jurisdiction_code", "")))
        if not isinstance(jurisdiction, Jurisdiction):
            return jurisdiction

        def build() -> JsonDict:
            answer = answer_project_question.execute(project_id, question, jurisdiction)
            return serializers.project_answer_json(answer)

        return errors.run_use_case(build)

    return bp
