"""`ClearanceSummaries` over both stores: the totals a project row draws.

The claim under test is not "the counting is right" -- `tests/unit/domain/
test_tracker.py` owns that, once, for the pure function both adapters call.
It is that each store answers for *many* projects in one call, reads nothing
it was not asked for, and agrees with the other about what an unanalysed
project looks like, so `GET /api/projects` cannot behave differently by mode.

Hand-written fakes over the same in-memory document boundary
`test_firestore_access.py` established, no `unittest.mock` (AGENT.md
Section 5). The fake records every read it serves, because "one batched read
of the project documents, then one stream per project" is a claim about
requests, not about return values, and nothing else in the result would show
it broken.
"""

from typing import Any

import pytest

from clearcut.adapters.demo.in_memory import InMemoryScriptStore, InMemoryTrackerStore
from clearcut.adapters.gcp.tracker import FirestoreTrackerStore
from clearcut.application.analysis_documents import tracker_data
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.tracker import ClearanceSummary, TrackerItem, TrackerState
from tests.unit.adapters.test_clearance_transactions import AtomicClient
from tests.unit.adapters.test_firestore_access import Ref

AT = "2026-09-06T10:00:00Z"


def item(
    project_id: str,
    item_id: str,
    state: TrackerState = TrackerState.BLOCKED,
    needs_review: bool = False,
    version: int = 1,
) -> TrackerItem:
    return TrackerItem(
        item_id,
        project_id,
        "finding-" + item_id,
        (1,),
        state,
        "permission",
        "rights@example.com",
        "",
        "",
        AT,
        version,
        needs_review=needs_review,
    )


class RecordingRef(Ref):
    """`Ref`, plus a note of every collection it streams."""

    def collection(self, name: str) -> "RecordingRef":
        return RecordingRef(self.client, self.path + "/" + name)

    def document(self, name: str) -> "RecordingRef":
        return RecordingRef(self.client, self.path + "/" + name)

    def stream(self) -> list[Ref]:
        self.client.reads.append("stream " + self.path)
        return super().stream()


class RecordingClient(AtomicClient):
    """The transactional fake, plus `get_all` -- the one batched read the
    summary path makes -- and a log of every read it served."""

    def __init__(self) -> None:
        super().__init__()
        self.reads: list[str] = []

    def collection(self, name: str) -> RecordingRef:
        return RecordingRef(self, name)

    def get_all(self, references: list[Any]) -> list[Any]:
        self.reads.append("get_all " + ",".join(sorted(ref.path for ref in references)))
        return list(references)


def store() -> tuple[RecordingClient, FirestoreTrackerStore]:
    """Three projects: one on the legacy `clearances` collection, one on a
    published generation with a producer override on top, and one with a
    project document and no clearance work at all."""
    client = RecordingClient()
    client.data = {
        "project_access/legacy": {"organization_id": "org", "grants": {}},
        "project_access/published": {
            "organization_id": "org",
            "grants": {},
            "active_generation": "gen-1",
        },
        "project_access/empty": {"organization_id": "org", "grants": {}},
    }
    tracker = FirestoreTrackerStore(client, InMemoryScriptStore())
    tracker.save(
        [
            item("legacy", "a", TrackerState.CLEARED),
            item("legacy", "b", TrackerState.BLOCKED),
            item("legacy", "c", TrackerState.CLEARED, needs_review=True),
        ]
    )
    generation = "project_access/published/clearance_generations/gen-1"
    for row in (item("published", "x"), item("published", "y", TrackerState.IN_PROGRESS)):
        client.data[f"{generation}/items/{row.item_id}"] = tracker_data(row)
    client.data[f"{generation}/overrides/x"] = tracker_data(
        item("published", "x", TrackerState.CLEARED, version=2)
    )
    client.reads.clear()
    return client, tracker


# --- The Firestore store ----------------------------------------------------


def test_one_call_answers_for_every_project_at_once() -> None:
    client, tracker = store()

    summaries = tracker.summaries_for_projects(["legacy", "published", "empty"])

    assert summaries["legacy"] == ClearanceSummary(
        total=3, cleared=1, in_progress=0, blocked=1, needs_review=1
    )
    assert summaries["published"] == ClearanceSummary(
        total=2, cleared=1, in_progress=1, blocked=0, needs_review=0
    )
    assert (
        client.reads.count(
            "get_all project_access/empty,project_access/legacy,project_access/published"
        )
        == 1
    )


def test_a_producers_override_replaces_the_published_item_it_supersedes() -> None:
    """`x` is BLOCKED in the generation and CLEARED in `overrides`. Counting
    both would report three items where the project has two."""
    _, tracker = store()

    summary = tracker.summaries_for_projects(["published"])["published"]

    assert summary.total == 2
    assert summary.cleared == 1


def test_an_analysed_project_with_no_items_is_zero_and_an_absent_one_is_left_out() -> None:
    """Zero items is an answer; a project that is not there is not one this
    store will pretend it read. The route fills either in with the same
    zeroes, so no client has to tell them apart."""
    _, tracker = store()

    summaries = tracker.summaries_for_projects(["empty", "never-existed"])

    assert summaries == {
        "empty": ClearanceSummary(total=0, cleared=0, in_progress=0, blocked=0, needs_review=0)
    }


def test_the_project_documents_are_read_in_one_batch_not_one_request_each() -> None:
    """The bound this store promises: one `get_all` for the whole list, then
    one stream per project that holds clearance work -- never a request per
    project just to learn where its items live."""
    client, tracker = store()

    tracker.summaries_for_projects(["legacy", "published", "empty"])

    assert len([read for read in client.reads if read.startswith("get_all ")]) == 1
    assert [read for read in client.reads if read.startswith("stream ")] == [
        "stream project_access/legacy/clearances",
        "stream project_access/published/clearance_generations/gen-1/items",
        "stream project_access/published/clearance_generations/gen-1/overrides",
        "stream project_access/empty/clearances",
    ]


def test_no_document_outside_the_requested_projects_is_ever_read() -> None:
    """The authorization claim, at the store: the ids the route was allowed to
    serve are the only paths this touches. Nothing here widens a query, and
    `published` is invisible to a caller that did not name it."""
    client, tracker = store()

    tracker.summaries_for_projects(["legacy"])

    assert "published" not in " ".join(client.reads)
    assert client.reads == [
        "get_all project_access/legacy",
        "stream project_access/legacy/clearances",
    ]


def test_an_id_shaped_like_a_path_is_refused_rather_than_resolved() -> None:
    """`legacy/clearances/a` would resolve to a document inside another
    project rather than to a project, so it never reaches Firestore."""
    client, tracker = store()

    assert tracker.summaries_for_projects(["published/clearance_generations"]) == {}
    assert client.reads == []


def test_no_ids_means_no_read_at_all() -> None:
    client, tracker = store()

    assert tracker.summaries_for_projects([]) == {}
    assert client.reads == []


def test_a_repeated_id_is_read_once() -> None:
    client, tracker = store()

    summaries = tracker.summaries_for_projects(["legacy", "legacy"])

    assert set(summaries) == {"legacy"}
    assert len([read for read in client.reads if read.startswith("stream ")]) == 1


def test_an_unavailable_store_surfaces_as_source_unavailable() -> None:
    class Broken(RecordingClient):
        def get_all(self, references: list[Any]) -> list[Any]:
            raise RuntimeError("no connection")

    client = Broken()
    client.data = {"project_access/legacy": {"organization_id": "org", "grants": {}}}
    tracker = FirestoreTrackerStore(client, InMemoryScriptStore())

    with pytest.raises(SourceUnavailable):
        tracker.summaries_for_projects(["legacy"])


# --- The demo store ---------------------------------------------------------


def demo() -> InMemoryTrackerStore:
    tracker = InMemoryTrackerStore()
    tracker.save(
        [
            item("one", "a", TrackerState.CLEARED),
            item("one", "b", TrackerState.IN_PROGRESS),
            item("two", "c", TrackerState.BLOCKED),
            item("two", "d", TrackerState.CLEARED, needs_review=True),
        ]
    )
    return tracker


def test_the_demo_store_answers_for_every_project_in_one_pass() -> None:
    summaries = demo().summaries_for_projects(["one", "two"])

    assert summaries["one"] == ClearanceSummary(
        total=2, cleared=1, in_progress=1, blocked=0, needs_review=0
    )
    assert summaries["two"] == ClearanceSummary(
        total=2, cleared=0, in_progress=0, blocked=1, needs_review=1
    )


def test_the_demo_store_counts_only_the_projects_it_was_asked_about() -> None:
    """Mock mode has no grants, but the port's contract is the same either
    way: an id the caller did not name is an id it does not get back."""
    summaries = demo().summaries_for_projects(["one"])

    assert set(summaries) == {"one"}


def test_neither_store_invents_a_summary_for_a_project_it_does_not_hold() -> None:
    """The one thing both must agree on: an id neither store knows comes back
    absent, never as a number the route would print as fact."""
    _, firestore_store = store()

    assert demo().summaries_for_projects(["nothing-here"]) == {}
    assert firestore_store.summaries_for_projects(["nothing-here"]) == {}
