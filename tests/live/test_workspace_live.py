"""Disposable private workspaces against the actual Firestore database."""

import uuid

import pytest
from google.cloud import firestore

from clearcut.adapters.gcp.firestore_access import FirestoreProjectAccess
from clearcut.domain.identity import AccessDenied
from clearcut.domain.project import Project
from tests.live.conftest import env, requires


@pytest.mark.live
@requires("GOOGLE_CLOUD_PROJECT")
def test_private_projects_require_membership_and_grants_in_live_firestore() -> None:
    client = firestore.Client(project=env("GOOGLE_CLOUD_PROJECT"))
    store = FirestoreProjectAccess(client)
    prefix = "clearcut-test-" + uuid.uuid4().hex
    organizations = [prefix + "-org-a", prefix + "-org-b"]
    users = [prefix + "-user-a", prefix + "-user-b"]
    projects = [prefix + "-project-a", prefix + "-project-b"]
    cleanup = []
    try:
        for org, user, project_id in zip(organizations, users, projects, strict=True):
            cleanup.extend(
                [
                    client.document(f"organizations/{org}"),
                    client.document(f"organizations/{org}/members/{user}"),
                    client.document(f"users/{user}/organizations/{org}"),
                    client.document(f"projects/{project_id}"),
                    client.document(f"project_access/{project_id}"),
                    client.document(f"users/{user}/projects/{project_id}"),
                    client.document(f"outbox/project-{project_id}"),
                ]
            )
            store.create_organization(user, org, "Disposable recovery acceptance")
            project = Project(project_id, "Synthetic test project", "AR", "2026-09-06T00:00:00Z")
            store.create_project(user, org, project)
            assert store.get_project(project_id) == project
            assert store.authorize(user, project_id, "read") == org
            snapshot = client.document(f"project_access/{project_id}").get()
            assert snapshot.update_time is not None  # Server commit timestamp.
        with pytest.raises(AccessDenied):
            store.authorize(users[0], projects[1], "read")
        extra = client.document(f"organizations/{organizations[0]}/members/{users[1]}")
        cleanup.append(extra)
        extra.create({"active": True, "role": "admin"})
        with pytest.raises(AccessDenied):
            store.authorize(users[1], projects[0], "read")
    finally:
        for ref in reversed(cleanup):
            ref.delete()
        assert not any(ref.get().exists for ref in cleanup)
