"""SDK transaction callbacks exercised against an in-memory document boundary.

This proves access decisions and atomic write grouping, not live Firestore IAM.
"""

from typing import Any

import pytest

from clearcut.adapters.gcp.firestore_access import FirestoreProjectAccess
from clearcut.domain.identity import AccessDenied
from clearcut.domain.project import Project


class Ref:
    def __init__(self, client: Any, path: str) -> None:
        self.client, self.path = client, path

    @property
    def id(self) -> str:
        return self.path.rsplit("/", 1)[-1]

    def collection(self, name: str) -> "Ref":
        return Ref(self.client, self.path + "/" + name)

    def document(self, name: str) -> "Ref":
        return Ref(self.client, self.path + "/" + name)

    def get(self, transaction: Any = None) -> "Ref":
        if transaction is not None:
            assert not transaction.writes, "transaction reads must precede writes"
        return self

    def to_dict(self) -> Any:
        return self.client.data.get(self.path)

    def set(self, data: Any) -> None:
        """Overwrites, unlike `create`. A favourite marked twice is the same
        favourite, so the second write must not fail the way `create` would."""
        self.client.data[self.path] = data

    def delete(self) -> None:
        self.client.data.pop(self.path, None)

    def stream(self) -> list["Ref"]:
        prefix = self.path + "/"
        return [
            Ref(self.client, path)
            for path in sorted(self.client.data)
            if path.startswith(prefix) and "/" not in path[len(prefix) :]
        ]


class Transaction:
    _read_only = False
    _max_attempts = 1
    _id = b"test-transaction"

    def __init__(self, client: Any) -> None:
        self.client = client
        self.writes: list[tuple[str, Any]] = []

    def _clean_up(self) -> None:
        self.writes = []

    def _begin(self, retry_id: Any = None) -> None:
        pass

    def create(self, ref: Ref, data: Any) -> None:
        self.writes.append((ref.path, data))

    def _commit(self) -> None:
        assert all(path not in self.client.data for path, _ in self.writes)
        self.client.data.update(self.writes)

    def _rollback(self) -> None:
        self.writes = []


class Client:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {}

    def collection(self, name: str) -> Ref:
        return Ref(self, name)

    def transaction(self) -> Transaction:
        return Transaction(self)


def configured() -> tuple[Client, FirestoreProjectAccess]:
    client = Client()
    client.data = {
        "project_access/one": {"organization_id": "org-one", "grants": {"alice": "producer"}},
        "organizations/org-one/members/alice": {"active": True, "role": "producer"},
        "organizations/org-one/members/bob": {"active": True, "role": "admin"},
    }
    return client, FirestoreProjectAccess(client)


def test_membership_even_admin_does_not_expose_private_project():
    _, access = configured()
    with pytest.raises(AccessDenied):
        access.authorize("bob", "one", "read")


def test_grant_and_active_membership_are_both_required_on_every_request():
    client, access = configured()
    assert access.authorize("alice", "one", "produce") == "org-one"
    client.data["organizations/org-one/members/alice"]["active"] = False
    with pytest.raises(AccessDenied):
        access.authorize("alice", "one", "read")


def test_unmapped_legacy_project_is_quarantined():
    _, access = configured()
    with pytest.raises(AccessDenied):
        access.authorize("alice", "legacy", "read")


def test_private_project_grant_index_and_outbox_commit_together():
    client, access = configured()
    project = Project("new", "Private draft", "AR", "2026-09-06T00:00:00Z")
    access.create_project("alice", "org-one", project)
    assert access.get_project("new") == project
    assert access.authorize("alice", "new", "read") == "org-one"
    assert "users/alice/projects/new" in client.data
    assert client.data["outbox/project-new"]["state"] == "pending"
    with pytest.raises(AccessDenied):
        access.authorize("bob", "new", "read")


def test_non_member_project_create_leaves_no_partial_records():
    client, access = configured()
    before = dict(client.data)
    with pytest.raises(AccessDenied):
        access.create_project("mallory", "org-one", Project("new", "Private", "AR", "now"))
    assert client.data == before


# --- Favourites -------------------------------------------------------------
#
# A favourite is one user's mark on a project, so it lives under the user and
# never on the project: a second producer reading the same project must not
# find the first one's bookmark.


def test_a_favourite_is_stored_under_the_user_and_comes_back_for_them_only():
    _, access = configured()
    access.add_favourite("alice", "one")

    assert access.favourites("alice") == {"one"}
    assert access.favourites("bob") == set()


def test_marking_the_same_project_twice_is_marking_it_once():
    """`PUT` is idempotent, so the second write overwrites rather than
    colliding the way a `create` would."""
    _, access = configured()
    access.add_favourite("alice", "one")
    access.add_favourite("alice", "one")

    assert access.favourites("alice") == {"one"}


def test_a_user_cannot_favourite_a_project_they_cannot_see():
    """`bob` is an active member of the same organization and still has no
    grant on `one`, which is the case `authorize` exists for. Nothing is
    written, so the marker cannot be used to confirm the project exists."""
    client, access = configured()
    before = dict(client.data)

    with pytest.raises(AccessDenied):
        access.add_favourite("bob", "one")

    assert client.data == before
    assert access.favourites("bob") == set()


def test_an_unmapped_legacy_project_cannot_be_favourited_either():
    _, access = configured()

    with pytest.raises(AccessDenied):
        access.add_favourite("alice", "legacy")


def test_a_favourite_is_cleared_and_clearing_an_unmarked_project_succeeds():
    """Removing is not authorized: a user who has lost access to a project
    must still be able to take it off their own list."""
    _, access = configured()
    access.add_favourite("alice", "one")

    access.remove_favourite("alice", "one")
    access.remove_favourite("alice", "one")

    assert access.favourites("alice") == set()


def test_the_project_document_never_carries_anybody_favourite():
    client, access = configured()
    project = Project("new", "Private draft", "AR", "2026-09-06T00:00:00Z")
    access.create_project("alice", "org-one", project)

    access.add_favourite("alice", "new")

    assert "favourite" not in client.data["projects/new"]


def test_the_three_optional_fields_round_trip_through_the_project_document():
    client, access = configured()
    project = Project(
        "new",
        "Private draft",
        "AR",
        "2026-09-06T00:00:00Z",
        poster_uri="gs://clearcut-posters/new.jpg",
        format="documentary",
        status="in_production",
    )

    access.create_project("alice", "org-one", project)

    assert access.get_project("new") == project
    assert client.data["projects/new"]["poster_uri"] == "gs://clearcut-posters/new.jpg"


def test_a_project_document_written_before_the_three_fields_still_reads():
    """`.get`, not `[...]`: a document from before this change carries none of
    them, and an unset poster is a real answer rather than a corrupt record."""
    client, access = configured()
    client.data["projects/old"] = {
        "project_id": "old",
        "title": "Legacy",
        "jurisdiction_code": "AR",
        "created_at": "2026-09-01T00:00:00Z",
    }

    project = access.get_project("old")

    assert (project.poster_uri, project.format, project.status) == (None, None, None)
