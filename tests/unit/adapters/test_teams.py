"""Invitation redemption, membership epochs and private grant transactions."""

from copy import deepcopy
from datetime import timedelta

import pytest

from clearcut.adapters.gcp.firestore_access import FirestoreProjectAccess
from clearcut.adapters.gcp.teams import FirestoreTeams
from clearcut.domain.identity import AccessDenied, Identity
from clearcut.domain.workspace import InvalidWorkspace, WorkspaceConflict
from tests.unit.adapters.test_clearance_transactions import AtomicClient
from tests.unit.adapters.test_durable_jobs import NOW


def configured() -> tuple[AtomicClient, FirestoreTeams, FirestoreProjectAccess]:
    client = AtomicClient()
    client.data = {
        "organizations/org": {"name": "Studio", "owner_id": "owner"},
        "organizations/org/members/owner": {"active": True, "role": "owner", "version": 1},
        "organizations/org/members/admin": {"active": True, "role": "admin", "version": 1},
        "organizations/org/members/producer": {"active": True, "role": "producer", "version": 1},
        "project_access/project": {"organization_id": "org", "grants": {"owner": "owner"}},
    }
    return client, FirestoreTeams(client), FirestoreProjectAccess(client)


def test_invitation_joins_no_projects_and_old_grants_never_revive_on_rejoin():
    client, teams, access = configured()
    identity = Identity("writer", "writer@example.com")
    teams.invite("owner", "org", "invite", "hash", identity.email, "writer", NOW)
    assert teams.accept(identity, "hash", NOW) == "org"
    before = deepcopy(client.data)
    assert teams.accept(identity, "hash", NOW) == "org"
    assert client.data == before
    with pytest.raises(AccessDenied):
        access.authorize("writer", "project", "read")
    teams.assign("owner", "project", "writer", "writer", 1, NOW)
    assert access.authorize("writer", "project", "script") == "org"
    teams.change_member("owner", "org", "writer", "writer", False, 1, NOW)
    with pytest.raises(AccessDenied):
        access.authorize("writer", "project", "read")
    teams.invite("owner", "org", "rejoin", "hash2", identity.email, "writer", NOW)
    teams.accept(identity, "hash2", NOW)
    with pytest.raises(AccessDenied):
        access.authorize("writer", "project", "read")
    teams.assign("owner", "project", "writer", "writer", 2, NOW)
    assert access.authorize("writer", "project", "read") == "org"


@pytest.mark.parametrize("failure", ["expired", "revoked", "wrong-email", "other-user"])
def test_unusable_invitation_never_creates_membership(failure):
    client, teams, _ = configured()
    teams.invite("owner", "org", "invite", "hash", "writer@example.com", "writer", NOW)
    at = NOW + timedelta(days=8) if failure == "expired" else NOW
    email = "other@example.com" if failure == "wrong-email" else "writer@example.com"
    if failure == "revoked":
        teams.revoke_invitation("owner", "org", "invite", 1, NOW)
    if failure == "other-user":
        teams.accept(Identity("first", email), "hash", NOW)
    before = deepcopy(client.data)
    with pytest.raises(InvalidWorkspace):
        teams.accept(Identity("writer", email), "hash", at)
    assert client.data == before


def test_owner_and_assignment_guards_leave_no_partial_audit_or_indexes():
    client, teams, _ = configured()
    before = deepcopy(client.data)
    with pytest.raises(InvalidWorkspace):
        teams.change_member("owner", "org", "owner", "viewer", False, 1, NOW)
    with pytest.raises(AccessDenied):
        teams.invite("producer", "org", "invite", "hash", "writer@example.com", "writer", NOW)
    with pytest.raises(AccessDenied):
        teams.assign("admin", "project", "producer", "writer", 1, NOW)
    with pytest.raises(InvalidWorkspace):
        teams.assign("owner", "project", "foreign-user", "viewer", 1, NOW)
    with pytest.raises(WorkspaceConflict):
        teams.assign("owner", "project", "producer", "writer", 4, NOW)
    assert client.data == before
