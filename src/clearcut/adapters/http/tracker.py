"""Tracker: the actionable side of a finding, and the actions taken on it.

Every path nests under the project that owns the item. The top-level
`/api/tracker-items/{item_id}` is gone: an item id is unique only inside its
project (`EVT-001` exists in every project that ran an analysis), so an id
alone left the server unable to answer "may this caller read it" without a
second lookup, and left ClickHouse free to merge two projects' rows into one.

`POST .../actions` is gone too, replaced by two sub-resources. An action verb
that dispatches on a body field is a remote procedure call wearing a
resource's clothes, and two of its four values were unimplemented and
answered 500. They now get no route at all: a 404 from routing says "this
does not exist" more honestly than a 500 from a handler that knows it does
not exist (ADR 0012).

Notifying writes nothing. `ResolveFinding` returns the item unchanged, and
the 201 reports that the webhook accepted the notification, not that the item
moved -- only a producer's own transition does that.
"""

from typing import Any

from flask import Blueprint
from flask.typing import ResponseReturnValue

from clearcut.adapters.http import errors, schemas, serializers, validators
from clearcut.application.get_tracker_item import GetTrackerItem
from clearcut.application.list_tracker_items import ListTrackerItems
from clearcut.application.resolve_finding import DraftEmail, Notify, ResolveFinding, Transition
from clearcut.domain.tracker import TrackerState

JsonDict = dict[str, Any]

TAG = "Tracker"

TAG_DESCRIPTION = "The actionable side of a finding, and the actions taken on it."

_ITEM_PATH = "/api/projects/{project_id}/tracker-items/{item_id}"

SCHEMAS: JsonDict = {
    "TrackerState": {
        "type": "string",
        "enum": ["BLOCKED", "IN_PROGRESS", "CLEARED"],
        "description": ("Where a tracker item stands. Every ordered pair is a legal transition."),
    },
    "TrackerItem": {
        "type": "object",
        "description": "The actionable side of a finding.",
        "required": [
            "item_id",
            "project_id",
            "finding_id",
            "scene_numbers",
            "state",
            "needs_review",
            "required_document",
            "contact",
            "litigation_posture",
            "draft_email",
            "note",
            "updated_at",
            "version",
        ],
        "properties": {
            "item_id": {"type": "string"},
            "project_id": {"type": "string"},
            "finding_id": {"type": "string"},
            "scene_numbers": {
                "type": "array",
                "description": (
                    "Every scene this item covers. More than one when the same asset "
                    "was deduplicated across scenes."
                ),
                "minItems": 1,
                "items": {"type": "integer", "minimum": 1},
            },
            "state": schemas.ref("TrackerState"),
            "needs_review": {
                "type": "boolean",
                "description": (
                    "A cleared item whose scene changed in a later version. It is neither "
                    "silently kept nor silently dropped: a producer looks at it again."
                ),
            },
            "required_document": {"type": "string"},
            "contact": {
                "type": "string",
                "description": "The rights holder to reach, as resolved by rights research.",
            },
            "litigation_posture": {
                "type": "string",
                "description": ("What the holder is known to have done about unlicensed use."),
            },
            "draft_email": {
                "description": (
                    "The outreach draft, once `email-drafts` has been posted. Null before "
                    "that. The system never sends it."
                ),
                "type": ["string", "null"],
            },
            "note": {
                "type": "string",
                "description": (
                    "Why this item is in the state it is, when a version was written for "
                    "a reason the state alone does not carry. Empty otherwise."
                ),
            },
            "updated_at": {"type": "string", "format": "date-time"},
            "version": {
                "type": "integer",
                "minimum": 1,
                "description": "Each action writes a new version rather than mutating this row.",
            },
        },
        "additionalProperties": False,
    },
    "TrackerItemStateUpdate": {
        "type": "object",
        "required": ["state"],
        "properties": {"state": schemas.ref("TrackerState")},
        "additionalProperties": False,
    },
    "NotificationCreate": {
        "type": "object",
        "required": ["reason"],
        "properties": {
            "reason": {
                "type": "string",
                "minLength": 1,
                "description": "What the producer is being told, in one sentence.",
            }
        },
        "additionalProperties": False,
    },
}

PATHS: JsonDict = {
    "/api/projects/{project_id}/tracker-items": {
        "parameters": [schemas.PROJECT_ID],
        "get": {
            "tags": [TAG],
            "operationId": "listTrackerItems",
            "summary": "This project's tracker items",
            "responses": {
                "200": schemas.ok(
                    "One entry per item, at its newest version. An empty array when the "
                    "project has no items.",
                    schemas.json_array_of(schemas.ref("TrackerItem")),
                ),
                "404": schemas.NOT_FOUND,
                "500": schemas.INTERNAL_ERROR,
            },
        },
    },
    _ITEM_PATH: {
        "parameters": [schemas.PROJECT_ID, schemas.ITEM_ID],
        "get": {
            "tags": [TAG],
            "operationId": "getTrackerItem",
            "summary": "One tracker item",
            "responses": {
                "200": schemas.ok(
                    "The item at its newest version.",
                    schemas.json_of(schemas.ref("TrackerItem")),
                ),
                "404": schemas.NOT_FOUND,
                "500": schemas.INTERNAL_ERROR,
            },
        },
        "patch": {
            "tags": [TAG],
            "operationId": "updateTrackerItemState",
            "summary": "Move one item between states",
            "description": (
                "Every ordered pair of states is legal, including back out of `CLEARED` "
                "and into the state the item already holds. A transition is an audit "
                "record of what a producer did, not a cache of where the item stands, so "
                "each one writes a new version."
            ),
            "requestBody": schemas.body(schemas.ref("TrackerItemStateUpdate")),
            "responses": {
                "200": schemas.ok(
                    "The item at its new version.",
                    schemas.json_of(schemas.ref("TrackerItem")),
                ),
                "400": schemas.failure("Missing or unrecognized `state`."),
                "404": schemas.NOT_FOUND,
                "500": schemas.INTERNAL_ERROR,
            },
        },
    },
    f"{_ITEM_PATH}/email-drafts": {
        "parameters": [schemas.PROJECT_ID, schemas.ITEM_ID],
        "post": {
            "tags": [TAG],
            "operationId": "createTrackerItemEmailDraft",
            "summary": "Draft the outreach email for one item",
            "description": (
                "Fills the outreach template from the item's rights holder, contact and "
                "required document, and stores it on the item as `draft_email`. The "
                "system never sends it: a producer copies the draft and sends it "
                "themselves."
            ),
            "responses": {
                "201": schemas.ok(
                    "The item at its new version, carrying the draft.",
                    schemas.json_of(schemas.ref("TrackerItem")),
                ),
                "404": schemas.NOT_FOUND,
                "500": schemas.INTERNAL_ERROR,
            },
        },
    },
    f"{_ITEM_PATH}/notifications": {
        "parameters": [schemas.PROJECT_ID, schemas.ITEM_ID],
        "post": {
            "tags": [TAG],
            "operationId": "createTrackerItemNotification",
            "summary": "Notify the producer about one item",
            "description": ("Posts the item and the reason to the configured outbound webhook."),
            "requestBody": schemas.body(schemas.ref("NotificationCreate")),
            "responses": {
                "201": schemas.ok(
                    "The item at its new version. The webhook accepted the notification.",
                    schemas.json_of(schemas.ref("TrackerItem")),
                ),
                "400": schemas.failure(
                    "`reason` is missing, blank, or whitespace only. A notification with "
                    "no reason tells the producer nothing an unsent one would not."
                ),
                "404": schemas.NOT_FOUND,
                "502": schemas.failure(
                    "The webhook rejected the notification. Nothing was recorded."
                ),
                "500": schemas.INTERNAL_ERROR,
            },
        },
    },
}


def create_tracker_blueprint(
    list_tracker_items: ListTrackerItems,
    get_tracker_item: GetTrackerItem,
    resolve_finding: ResolveFinding,
) -> Blueprint:
    bp = Blueprint("clearcut_tracker", __name__)
    item_route = "/api/projects/<project_id>/tracker-items/<item_id>"

    @bp.route("/api/projects/<project_id>/tracker-items", methods=["GET"])
    def tracker_index(project_id: str) -> ResponseReturnValue:
        def build() -> list[JsonDict]:
            items = list_tracker_items.execute(project_id)
            return [serializers.tracker_item_json(item) for item in items]

        return errors.run_use_case(build)

    @bp.route(item_route, methods=["GET"])
    def tracker_show(project_id: str, item_id: str) -> ResponseReturnValue:
        return errors.run_use_case(
            lambda: serializers.tracker_item_json(get_tracker_item.execute(project_id, item_id))
        )

    @bp.route(item_route, methods=["PATCH"])
    def tracker_patch(project_id: str, item_id: str) -> ResponseReturnValue:
        state = validators.require_state(validators.json_body())
        if not isinstance(state, TrackerState):
            return state
        at = validators.now()

        def build() -> JsonDict:
            item = resolve_finding.execute(project_id, item_id, Transition(state), at)
            return serializers.tracker_item_json(item)

        return errors.run_use_case(build)

    @bp.route(f"{item_route}/email-drafts", methods=["POST"])
    def email_drafts_create(project_id: str, item_id: str) -> ResponseReturnValue:
        at = validators.now()

        def build() -> JsonDict:
            item = resolve_finding.execute(project_id, item_id, DraftEmail(), at)
            return serializers.tracker_item_json(item)

        return errors.run_use_case(build, status=201)

    @bp.route(f"{item_route}/notifications", methods=["POST"])
    def notifications_create(project_id: str, item_id: str) -> ResponseReturnValue:
        reason = validators.require_field(validators.json_body(), "reason")
        if not isinstance(reason, str):
            return reason
        at = validators.now()

        def build() -> JsonDict:
            item = resolve_finding.execute(project_id, item_id, Notify(reason), at)
            return serializers.tracker_item_json(item)

        return errors.run_use_case(build, status=201)

    return bp
