"""Literal private-project search over saved screenplay and recorded workspace data."""

import base64
import hashlib
import json
import unicodedata
from typing import Any

from clearcut.application.document_ports import ProjectDocuments
from clearcut.application.draft_ports import DraftStore, ScreenplayContent
from clearcut.application.list_tracker_items import ListTrackerItems
from clearcut.application.local_research_ports import LocalResearchStore
from clearcut.domain.workspace import InvalidWorkspace, WorkspaceConflict


def normalized(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c)
    )


def excerpt(value: str, needle: str) -> str:
    folded: list[str] = []
    positions: list[int] = []
    for index, character in enumerate(value):
        part = normalized(character)
        folded.append(part)
        positions.extend([index] * len(part))
    match = "".join(folded).find(needle)
    start = max(0, positions[match] - 100) if match >= 0 else 0
    return (
        ("…" if start else "")
        + value[start : start + 500]
        + ("…" if len(value) > start + 500 else "")
    )


class SearchProject:
    def __init__(
        self,
        drafts: DraftStore,
        content: ScreenplayContent,
        tracker: ListTrackerItems,
        documents: ProjectDocuments,
        research: LocalResearchStore | None = None,
    ) -> None:
        self.drafts, self.content, self.tracker = drafts, content, tracker
        self.documents, self.research = documents, research

    def execute(self, project_id: str, query: str, cursor: str | None = None) -> dict[str, Any]:
        if not isinstance(query, str) or not 2 <= len(query.strip()) <= 200:
            raise InvalidWorkspace("search requires 2–200 characters")
        needle = normalized(query.strip())
        if not needle:
            raise InvalidWorkspace("search requires visible characters")
        results: list[dict[str, Any]] = []

        def match(
            kind: str,
            identity: str,
            title: str,
            body: str,
            *,
            search_title: bool = True,
            **context: Any,
        ) -> None:
            if needle in normalized((title + "\n" if search_title else "") + body):
                # Select a matching paragraph when possible without returning entire scripts.
                paragraph = next(
                    (line for line in body.splitlines() if needle in normalized(line)), body
                )
                results.append(
                    {
                        "kind": kind,
                        "id": identity,
                        "title": title[:500],
                        "excerpt": excerpt(paragraph, needle),
                        **context,
                    }
                )

        revisions = self.drafts.revisions(project_id)
        revision = revisions[0] if revisions else None
        if revision:
            document = json.loads(self.content.get(revision.content))
            heading = ""
            for block in document["content"]:
                attrs = block["attrs"]
                body = "".join(node.get("text", "\n") for node in block.get("content", []))
                if attrs["kind"] == "scene-heading":
                    heading = body
                match(
                    "script",
                    attrs["blockId"],
                    heading,
                    body,
                    search_title=False,
                    revision_id=revision.revision_id,
                    scene_id=attrs["sceneId"],
                )
        for item in self.tracker.execute(project_id):
            body = "\n".join(
                str(value or "")
                for value in (
                    item.required_document,
                    item.note,
                    item.clearance_conditions,
                    item.contact,
                    item.draft_email,
                    item.assignee_id,
                    item.due_date,
                )
            )
            match("clearance", item.item_id, item.item_id, body, version=item.version)
        before: str | None = None
        while True:
            document_page = self.documents.list(project_id, before)
            for record in document_page:
                match("document", record.file_id, record.filename, record.kind)
            if len(document_page) < 50:
                break
            next_before = document_page[-1].file_id
            if next_before == before:
                raise WorkspaceConflict("document listing changed; restart the search")
            before = next_before
        if self.research is not None:
            for research_record in self.research.list(project_id):
                match(
                    "research",
                    research_record["research_id"],
                    research_record["question"],
                    research_record["text"],
                    settings_version=research_record["settings_version"],
                )
        results.sort(key=lambda result: (result["kind"], result["id"]))
        fingerprint = hashlib.sha256(
            json.dumps([project_id, needle, results], sort_keys=True).encode()
        ).hexdigest()
        offset = 0
        if cursor:
            try:
                decoded = json.loads(base64.urlsafe_b64decode(cursor.encode()))
                offset = decoded["offset"]
                if decoded["fingerprint"] != fingerprint:
                    raise WorkspaceConflict("search results changed; restart the search")
                if type(offset) is not int or not 0 <= offset <= len(results):
                    raise ValueError("invalid offset")
            except (ValueError, KeyError, TypeError, UnicodeError):
                raise InvalidWorkspace("invalid search cursor") from None
        page = results[offset : offset + 50]
        next_cursor = None
        if offset + 50 < len(results):
            next_cursor = base64.urlsafe_b64encode(
                json.dumps({"offset": offset + 50, "fingerprint": fingerprint}).encode()
            ).decode()
        return {
            "results": page,
            "total": len(results),
            "next_cursor": next_cursor,
            "revision_id": revision.revision_id if revision else None,
            "coverage": [
                "latest_saved_revision",
                "current_clearances",
                "document_names",
                "latest_50_local_research",
            ],
        }
