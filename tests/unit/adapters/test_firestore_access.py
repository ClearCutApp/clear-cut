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
