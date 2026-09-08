"""Transactional clearance authority; ClickHouse remains a downstream projection.

The legacy script store is injected until immutable analysis publication replaces
it. Clearance transactions never send webhooks or contact external providers.
"""

from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from clearcut.application.ports import ScriptStore
from clearcut.domain.activity import activity_envelope
from clearcut.domain.durable_analysis import ClearanceSnapshot
from clearcut.domain.errors import RecordNotFound, SourceUnavailable
from clearcut.domain.finding import Citation
from clearcut.domain.identity import AccessDenied, project_permits
from clearcut.domain.screenplay import ContentReference
from clearcut.domain.script import Script
from clearcut.domain.tracker import (
    ClearanceSummary,
    TrackerConflict,
    TrackerItem,
    TrackerState,
    clearance_summary,
)


def _item(data: dict[str, Any]) -> TrackerItem:
    return TrackerItem(
        **{
            **data,
            "state": TrackerState(data["state"]),
            "scene_numbers": tuple(data["scene_numbers"]),
            "evidence_file_ids": tuple(data.get("evidence_file_ids", [])),
            "rights_holder_citations": tuple(
                Citation(**citation) for citation in data.get("rights_holder_citations", [])
            ),
        }
    )


def _data(item: TrackerItem) -> dict[str, Any]:
    return {
        **asdict(item),
        "state": item.state.value,
        "scene_numbers": list(item.scene_numbers),
        "evidence_file_ids": list(item.evidence_file_ids),
        "rights_holder_citations": [asdict(citation) for citation in item.rights_holder_citations],
    }


class FirestoreTrackerStore:
    def __init__(self, client: Any, scripts: ScriptStore) -> None:
        self._client, self._scripts = client, scripts

    def _project(self, project_id: str) -> Any:
        return self._client.collection("project_access").document(project_id)

    def latest(self, project_id: str, item_id: str) -> TrackerItem:
        project = self._project(project_id)

        @firestore.transactional
        def read(transaction: Any) -> TrackerItem:
            scope = project.get(transaction=transaction).to_dict() or {}
            generation = scope.get("active_generation", "")
            root = (
                project.collection("clearance_generations").document(generation)
                if generation
                else project
            )
            base = (
                root.collection("items" if generation else "clearances")
                .document(item_id)
                .get(transaction=transaction)
                .to_dict()
            )
            override = (
                root.collection("overrides")
                .document(item_id)
                .get(transaction=transaction)
                .to_dict()
                if generation
                else None
            )
            data = override or base
            if not data:
                raise RecordNotFound("clearance not found")
            return _item(data)

        try:
            result: TrackerItem = read(self._client.transaction())
            return result
        except RecordNotFound:
            raise
        except Exception as exc:
            raise SourceUnavailable("clearance lookup unavailable") from exc

    def latest_for_project(self, project_id: str) -> list[TrackerItem]:
        return self.snapshot(project_id)[1]

    def _scopes(self, project_ids: list[str]) -> dict[str, dict[str, Any]]:
        """The `project_access` documents for `project_ids`, in one batched read.

        `get_all` is a single request for the whole list, where a loop of
        `.get()` would be one request per project. Documents come back in
        whatever order the backend answers in, and a project that does not
        exist comes back empty, so both are resolved by id here rather than
        by position.
        """
        references = [self._project(project_id) for project_id in project_ids]
        wanted = set(project_ids)
        scopes: dict[str, dict[str, Any]] = {}
        for document in self._client.get_all(references):
            data = document.to_dict()
            if data and document.id in wanted:
                scopes[document.id] = data
        return scopes

    def summaries_for_projects(self, project_ids: Sequence[str]) -> dict[str, ClearanceSummary]:
        """The clearance totals for every project in `project_ids`.

        **This is not one round trip, and Firestore cannot make it one.** The
        active generation id lives in each `project_access` document and forms
        part of the path its items are stored under
        (`clearance_generations/{generation}/items`), so the store cannot name
        the collections to read until it has read the project documents --
        and two projects on different generations share no collection to read
        together. What this does instead is bound the cost: one batched
        `get_all` for the project documents, then one stream per project that
        holds clearance work. The route above it still asks once, so no cost
        is paid per row in the browser.

        The alternative -- a collection group query on `project_id` across
        `clearances`, `items` and `overrides` -- was rejected on purpose. It
        needs three collection-group-scoped indexes that
        `infra/provision_runtime_indexes.py` does not provision, which would
        make the home screen fail in production until somebody created them by
        hand; and because the generation is in the path rather than in a
        field, it would read every superseded generation's items and throw
        most of them away.

        Unlike `snapshot`, this does not re-read the epoch to prove the list
        did not move underneath it. A total on a list screen is a display
        number a producer scans; the tracker page is where they act, and that
        page still reads through `snapshot`. Paying for a consistency proof
        per project here would double the reads to make a bar one pixel
        truer.

        A project whose document exists but holds no clearance work comes
        back as zeroes; an id with no project document at all is left out.
        Neither is a claim the caller has to tell apart -- it fills a missing
        id in with `EMPTY_CLEARANCE_SUMMARY` -- but reading a project that is
        not there is not something this store will pretend it did.
        """
        ids = [
            project_id
            for project_id in dict.fromkeys(project_ids)
            # A slash would resolve to a subcollection of another document,
            # so an id shaped like a path is refused rather than read.
            if project_id and "/" not in project_id and "\\" not in project_id
        ]
        if not ids:
            return {}
        try:
            scopes = self._scopes(ids)
            summaries: dict[str, ClearanceSummary] = {}
            for project_id, scope in scopes.items():
                generation = scope.get("active_generation", "")
                project = self._project(project_id)
                root = (
                    project.collection("clearance_generations").document(generation)
                    if generation
                    else project
                )
                items = {
                    item.item_id: item
                    for item in (
                        _item(row.to_dict())
                        for row in root.collection("items" if generation else "clearances").stream()
                    )
                }
                if generation:
                    for row in root.collection("overrides").stream():
                        override = _item(row.to_dict())
                        items[override.item_id] = override
                summaries[project_id] = clearance_summary(items.values())
            return summaries
        except Exception as exc:
            raise SourceUnavailable("clearance totals unavailable") from exc

    def snapshot(self, project_id: str) -> tuple[ClearanceSnapshot, list[TrackerItem]]:
        project = self._project(project_id)
        try:
            for _ in range(3):
                scope = project.get().to_dict() or {}
                generation = scope.get("active_generation", "")
                epoch = int(scope.get("clearance_epoch", 0))
                root = (
                    project.collection("clearance_generations").document(generation)
                    if generation
                    else project
                )
                values = [
                    _item(row.to_dict())
                    for row in root.collection("items" if generation else "clearances").stream()
                ]
                items = {item.item_id: item for item in values}
                if generation:
                    for row in root.collection("overrides").stream():
                        item = _item(row.to_dict())
                        items[item.item_id] = item
                after = project.get().to_dict() or {}
                if (
                    after.get("active_generation", "") == generation
                    and int(after.get("clearance_epoch", 0)) == epoch
                ):
                    reference = (
                        ContentReference(**scope["analysis_manifest"])
                        if scope.get("analysis_manifest")
                        else None
                    )
                    return ClearanceSnapshot(
                        generation, epoch, reference, scope.get("production_context_json", "{}")
                    ), sorted(items.values(), key=lambda item: item.item_id)
            raise TrackerConflict(int(after.get("clearance_epoch", 0)))
        except TrackerConflict:
            raise
        except Exception as exc:
            raise SourceUnavailable("clearance list unavailable") from exc

    def save(self, items: list[TrackerItem]) -> None:
        if not items:
            return
        self._write(items, actor=None)

    def compare_save(self, item: TrackerItem, expected_version: int, actor: str) -> None:
        if item.version != expected_version + 1:
            raise TrackerConflict(expected_version)
        self._write([item], actor=actor)

    def compare_reconfirm(
        self,
        item: TrackerItem,
        expected_version: int,
        actor: str,
        generation_id: str,
        revision_id: str,
        production_context_json: str = "{}",
    ) -> None:
        if item.version != expected_version + 1 or not generation_id or not revision_id:
            raise TrackerConflict(expected_version)
        self._write(
            [item], actor=actor, confirmation=(generation_id, revision_id, production_context_json)
        )

    def _write(
        self,
        items: list[TrackerItem],
        actor: str | None,
        confirmation: tuple[str, str, str] | None = None,
    ) -> None:
        project_id = items[0].project_id
        if len(items) > 150 or any(item.project_id != project_id for item in items):
            raise ValueError("one clearance transaction requires one project and at most 150 items")
        if len({item.item_id for item in items}) != len(items):
            raise ValueError("duplicate clearance identifiers")
        project = self._project(project_id)

        @firestore.transactional
        def write(transaction: Any) -> None:
            scope = project.get(transaction=transaction).to_dict()
            if not scope:
                raise AccessDenied()
            organization_id = scope["organization_id"]
            generation = scope.get("active_generation", "")
            if confirmation is not None and (
                generation != confirmation[0]
                or scope.get("production_context_json", "{}") != confirmation[2]
            ):
                raise TrackerConflict(items[0].version - 1)
            if generation and actor is None:
                raise ValueError("analysis changes require generation publication")
            root = (
                project.collection("clearance_generations").document(generation)
                if generation
                else project
            )
            refs = [
                root.collection("overrides" if generation else "clearances").document(item.item_id)
                for item in items
            ]
            event_refs = [
                root.collection("items" if generation else "clearances").document(item.item_id)
                for item in items
            ]
            if actor is not None:
                membership = (
                    self._client.collection("organizations")
                    .document(organization_id)
                    .collection("members")
                    .document(actor)
                    .get(transaction=transaction)
                    .to_dict()
                    or {}
                )
                if not project_permits(scope, membership, actor, "produce"):
                    raise AccessDenied()
            # Read every linked record before any mutation: evidence cannot cross
            # the project/organization boundary or be a browser storage URI.
            if actor is not None:
                for item in items:
                    if item.assignee_id:
                        member = (
                            self._client.collection("organizations")
                            .document(organization_id)
                            .collection("members")
                            .document(item.assignee_id)
                            .get(transaction=transaction)
                            .to_dict()
                            or {}
                        )
                        if not project_permits(scope, member, item.assignee_id, "read"):
                            raise AccessDenied()
                    for file_id in item.evidence_file_ids:
                        document = (
                            project.collection("documents")
                            .document(file_id)
                            .get(transaction=transaction)
                            .to_dict()
                            or {}
                        )
                        if (
                            document.get("project_id") != project_id
                            or document.get("organization_id") != organization_id
                            or not document.get("sha256")
                        ):
                            raise RecordNotFound("evidence file not found in this project")
            previous = [ref.get(transaction=transaction).to_dict() for ref in refs]
            if generation:
                bases = [ref.get(transaction=transaction).to_dict() for ref in event_refs]
                previous = [
                    override or base for override, base in zip(previous, bases, strict=True)
                ]
            changes = []
            for item, ref, old in zip(items, refs, previous, strict=True):
                version = int(old["version"]) if old else 0
                # A retried system publication is harmless only when identical.
                if actor is None and old == _data(item):
                    continue
                if version != item.version - 1:
                    raise TrackerConflict(version)
                changes.append((item, ref))
            if not changes:
                return
            events = {item.item_id: ref for item, ref in zip(items, event_refs, strict=True)}
            for item, ref in changes:
                data = _data(item)
                event_id = f"clearance-{project_id}-{item.item_id}-{item.version}"
                transaction.set(ref, data)
                transaction.create(
                    events[item.item_id].collection("events").document(str(item.version)),
                    {
                        "event_id": event_id,
                        "actor": actor or "analysis",
                        "version": item.version,
                        "previous_version": item.version - 1,
                        "at": item.updated_at,
                        "item": data,
                        **(
                            {
                                "action": "clearance_reconfirmed",
                                "generation_id": confirmation[0],
                                "revision_id": confirmation[1],
                            }
                            if confirmation
                            else {}
                        ),
                    },
                )
                payload = {
                    "item_id": item.item_id,
                    "state": item.state.value,
                    "needs_review": item.needs_review,
                }
                transaction.create(
                    self._client.collection("outbox").document(event_id),
                    activity_envelope(
                        event_id,
                        organization_id,
                        project_id,
                        "clearance_changed",
                        item.updated_at,
                        item.version,
                        payload,
                    ),
                )
            transaction.update(
                project, {"clearance_epoch": int(scope.get("clearance_epoch", 0)) + 1}
            )

        try:
            write(self._client.transaction())
        except (AccessDenied, TrackerConflict, RecordNotFound):
            raise
        except Exception as exc:
            raise SourceUnavailable("clearance write unavailable") from exc

    def history(
        self, project_id: str, item_id: str, before_version: int | None = None
    ) -> list[dict[str, Any]]:
        self.latest(project_id, item_id)
        try:
            project = self._project(project_id)
            scope = project.get().to_dict() or {}
            generation = scope.get("active_generation", "")
            seen: set[str] = set()
            events: dict[int, dict[str, Any]] = {}
            while True:
                if generation in seen:
                    raise SourceUnavailable("clearance history chain is invalid")
                seen.add(generation)
                root = (
                    project.collection("clearance_generations").document(generation)
                    if generation
                    else project
                )
                metadata = root.get().to_dict() if generation else {}
                if generation and (not metadata or metadata.get("state") != "committed"):
                    raise SourceUnavailable("clearance history generation is unavailable")
                query = (
                    root.collection("items" if generation else "clearances")
                    .document(item_id)
                    .collection("events")
                )
                if before_version is not None:
                    query = query.where(filter=FieldFilter("version", "<", before_version))
                for row in (
                    query.order_by("version", direction=firestore.Query.DESCENDING)
                    .limit(50)
                    .stream()
                ):
                    event = row.to_dict()
                    events.setdefault(int(event["version"]), event)
                if len(events) >= 50 or not generation:
                    break
                generation = (metadata or {}).get("parent_generation", "")
            return sorted(events.values(), key=lambda event: int(event["version"]), reverse=True)[
                :50
            ]
        except Exception as exc:
            raise SourceUnavailable("clearance history unavailable") from exc

    def record_script(self, script: Script) -> None:
        self._scripts.save(script)

    def latest_script(self, project_id: str) -> Script | None:
        return self._scripts.latest(project_id)
