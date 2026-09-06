"""Bible: the project facts continuity and policy audits run against.

The second endpoint ADR 0011 cut and ADR 0012 reinstated. Without a write
path, CONTINUITY findings only ever fired for the one project an operator had
seeded by hand from `infra/seed_project_bible.py`, which made the whole
continuity feature invisible to anyone using the product.

The server assigns `fact_id` as the next `FACT-NNN` in the project's own
sequence. A client-supplied id would let two producers write `FACT-007` twice
and leave a continuity finding citing whichever one survived.
"""

from typing import Any

from flask import Blueprint
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import errors, schemas, serializers, validators
from clearcut.application.add_bible_facts import AddBibleFacts, FactDraft
from clearcut.application.get_bible import GetBible
from clearcut.domain.bible import FactKind

JsonDict = dict[str, Any]

TAG = "Bible"

TAG_DESCRIPTION = "Project bible facts that continuity and policy audits run against."

SCHEMAS: JsonDict = {
    "BibleFactCreate": {
        "type": "object",
        "required": ["kind", "text", "source"],
        "properties": {
            "kind": schemas.ref("FactKind"),
            "text": {"type": "string", "minLength": 1},
            "source": {
                "type": "string",
                "minLength": 1,
                "description": (
                    "Where the fact comes from, so a finding that cites it can be checked."
                ),
            },
        },
        "additionalProperties": False,
    },
    "ProjectBible": {
        "type": "object",
        "required": ["project_id", "facts"],
        "properties": {
            "project_id": {"type": "string"},
            "facts": {
                "type": "array",
                "description": (
                    "Every fact recorded for this project. `fact_id` is unique within it."
                ),
                "items": schemas.ref("BibleFact"),
            },
        },
        "additionalProperties": False,
    },
}

PATHS: JsonDict = {
    "/api/projects/{project_id}/bible": {
        "parameters": [schemas.PROJECT_ID],
        "get": {
            "tags": [TAG],
            "operationId": "getProjectBible",
            "summary": "This project's bible",
            "responses": {
                "200": schemas.ok(
                    "The bible, with an empty `facts` array when nothing has been recorded.",
                    schemas.json_of(schemas.ref("ProjectBible")),
                ),
                "404": schemas.NOT_FOUND,
                "500": schemas.INTERNAL_ERROR,
            },
        },
    },
    "/api/projects/{project_id}/bible/facts": {
        "parameters": [schemas.PROJECT_ID],
        "post": {
            "tags": [TAG],
            "operationId": "createBibleFact",
            "summary": "Record one bible fact",
            "description": (
                "The server assigns `fact_id` as the next `FACT-NNN` in the project's "
                "sequence. A `LORE` fact feeds the continuity audit; a `POLICY` fact "
                "feeds the policy audit."
            ),
            "requestBody": schemas.body(schemas.ref("BibleFactCreate")),
            "responses": {
                "201": schemas.ok(
                    "The fact as stored, carrying the id the server assigned.",
                    schemas.json_of(schemas.ref("BibleFact")),
                ),
                "400": schemas.failure(
                    "`text` or `source` is missing, blank, or whitespace only. A fact "
                    "with no source cannot be cited, and a citation is what makes an "
                    "audit finding answerable."
                ),
                "404": schemas.NOT_FOUND,
                "500": schemas.INTERNAL_ERROR,
            },
        },
    },
}


def create_bible_blueprint(get_bible: GetBible, add_bible_facts: AddBibleFacts) -> Blueprint:
    bp = Blueprint("clearcut_bible", __name__)

    @bp.route("/api/projects/<project_id>/bible", methods=["GET"])
    def bible_show(project_id: str) -> ResponseReturnValue:
        return errors.run_use_case(
            lambda: serializers.project_bible_json(get_bible.execute(project_id))
        )

    @bp.route("/api/projects/<project_id>/bible/facts", methods=["POST"])
    def bible_facts_create(project_id: str) -> ResponseReturnValue:
        payload = validators.json_body()
        kind = validators.require_fact_kind(payload)
        if not isinstance(kind, FactKind):
            return kind
        text = validators.require_field(payload, "text")
        if not isinstance(text, str):
            return text
        source = validators.require_field(payload, "source")
        if not isinstance(source, str):
            return source
        draft = FactDraft(kind=kind, text=text, source=source)

        def build() -> JsonDict:
            # One fact per request, so the use case's list answer has exactly
            # one entry. It stays plural because numbering a batch is one
            # read of the project's sequence rather than one per fact, which
            # is what `infra/seed_project_bible.py` needs.
            created = add_bible_facts.execute(project_id, [draft])
            return serializers.bible_fact_json(created[0])

        return errors.run_use_case(build, status=201)

    return bp
