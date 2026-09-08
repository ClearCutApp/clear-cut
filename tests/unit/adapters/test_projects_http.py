"""The projects routes, over both persistence generations.

`create_projects_blueprint` serves two wirings and must answer the same shape
either way: mock mode drives the ClickHouse-era use cases over an in-memory
store with no identity at all, and live mode bypasses them for
`ProjectAccess`. A field that reached one path and not the other would be a
field the SPA can only draw against one deployment, so every assertion about
the three optional fields is made twice here.

Hand-written fakes, no `unittest.mock` (AGENT.md Section 5). The live path
mounts the real identity boundary rather than planting `g.identity`, because
"a user may only favourite a project they can see" is a claim about that
boundary and the adapter together.
"""

from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient

from clearcut.adapters.demo.in_memory import InMemoryProjectFavourites, InMemoryProjectStore
from clearcut.adapters.http.identity import install_identity_boundary
from clearcut.adapters.http.projects import create_projects_blueprint
from clearcut.adapters.http.serializers import project_json
from clearcut.application.create_project import CreateProject
from clearcut.application.get_project import GetProject
from clearcut.application.list_projects import ListProjects
from clearcut.domain.identity import AccessDenied, AuthenticationRequired, Identity, permits
from clearcut.domain.project import Project

AT = "2026-09-05T12:00:00Z"

PROJECT_FIELDS = {
    "project_id",
    "title",
    "jurisdiction_code",
    "created_at",
    "poster_uri",
    "format",
    "status",
    "favourite",
}


# --- The serializer ---------------------------------------------------------


def test_project_json_carries_every_field_with_nulls_for_the_unset_ones() -> None:
    """Always present, never omitted: a client that had to tell "absent" from
    "not set" apart would be writing the rule this API should state."""
    body = project_json(Project("prj-1", "Nocturne", "AR", AT))

    assert set(body) == PROJECT_FIELDS
    assert body["poster_uri"] is None
    assert body["format"] is None
    assert body["status"] is None
    assert body["favourite"] is False


def test_project_json_passes_the_three_fields_through_unchanged() -> None:
    body = project_json(
        Project("prj-1", "Nocturne", "AR", AT, "gs://posters/1.jpg", "documentary", "completed")
    )

    assert body["poster_uri"] == "gs://posters/1.jpg"
    assert body["format"] == "documentary"
    assert body["status"] == "completed"


def test_the_favourite_flag_is_the_callers_answer_not_the_projects() -> None:
    """The same project serialized for two callers carries two values, which
    is why it is an argument rather than a field of `Project`."""
    project = Project("prj-1", "Nocturne", "AR", AT)

    assert project_json(project, favourite=True)["favourite"] is True
    assert project_json(project, favourite=False)["favourite"] is False


# --- Mock mode: no identity, no access port ---------------------------------


def _mock_client(*projects: Project) -> tuple[FlaskClient, InMemoryProjectStore]:
    store = InMemoryProjectStore()
    for project in projects:
        store.save(project)
    app = Flask(__name__)
    app.register_blueprint(
        create_projects_blueprint(
            CreateProject(store),
            ListProjects(store),
            GetProject(store),
            None,
            InMemoryProjectFavourites(store),
        )
    )
    return app.test_client(), store


def test_mock_mode_lists_and_shows_the_three_fields() -> None:
    client, _ = _mock_client(Project("prj-1", "Nocturne", "AR", AT, "gs://p/1.jpg", "short", None))

    listed = client.get("/api/projects").get_json()
    shown = client.get("/api/projects/prj-1").get_json()

    found = next(item for item in listed if item["project_id"] == "prj-1")
    assert found["poster_uri"] == "gs://p/1.jpg"
    assert found["format"] == "short"
    assert found["status"] is None
    assert shown == found


def test_mock_mode_creates_a_project_carrying_all_three() -> None:
    client, store = _mock_client()

    response = client.post(
        "/api/projects",
        json={
            "title": "Nocturne",
            "jurisdiction_code": "AR",
            "poster_uri": "gs://p/new.jpg",
            "format": "series",
            "status": "in_production",
        },
    )

    assert response.status_code == 201
    body = response.get_json()
    assert (body["poster_uri"], body["format"], body["status"]) == (
        "gs://p/new.jpg",
        "series",
        "in_production",
    )
    assert store.get(body["project_id"]).format == "series"


def test_mock_mode_creates_a_project_with_none_of_them_exactly_as_before() -> None:
    """The backward-compatibility case: a client that has never heard of the
    three fields creates the project it always did."""
    client, _ = _mock_client()

    body = client.post("/api/projects", json={"title": "Nocturne", "jurisdiction_code": "AR"})

    assert body.status_code == 201
    assert body.get_json()["poster_uri"] is None
    assert body.get_json()["format"] is None


@pytest.mark.parametrize(
    "field,value", [("format", "feature-film"), ("status", "shooting"), ("poster_uri", 7)]
)
def test_an_unacceptable_optional_field_is_a_400_not_a_500(field: str, value: Any) -> None:
    """The domain refuses it too, but its `ValueError` reaches `run_use_case`
    as a 500 -- and a misspelled format is a request the client can fix."""
    client, _ = _mock_client()

    response = client.post(
        "/api/projects", json={"title": "N", "jurisdiction_code": "AR", field: value}
    )

    assert response.status_code == 400
    assert field in response.get_json()["error"]


def test_mock_mode_marks_and_clears_a_favourite() -> None:
    client, _ = _mock_client(Project("prj-1", "Nocturne", "AR", AT))

    marked = client.put("/api/projects/prj-1/favourite")
    listed = client.get("/api/projects").get_json()
    cleared = client.delete("/api/projects/prj-1/favourite")

    assert marked.get_json() == {"project_id": "prj-1", "favourite": True}
    assert next(item for item in listed if item["project_id"] == "prj-1")["favourite"] is True
    assert cleared.get_json() == {"project_id": "prj-1", "favourite": False}
    assert client.get("/api/projects/prj-1").get_json()["favourite"] is False


def test_mock_mode_marking_twice_and_clearing_twice_both_succeed() -> None:
    client, _ = _mock_client(Project("prj-1", "Nocturne", "AR", AT))

    assert client.put("/api/projects/prj-1/favourite").status_code == 200
    assert client.put("/api/projects/prj-1/favourite").status_code == 200
    assert client.delete("/api/projects/prj-1/favourite").status_code == 200
    assert client.delete("/api/projects/prj-1/favourite").status_code == 200


def test_mock_mode_refuses_to_favourite_a_project_it_does_not_hold() -> None:
    """Mock mode has no grants, so "a project this caller can see" is "a
    project this store knows about" -- the same 404 the live path gives."""
    client, _ = _mock_client()

    assert client.put("/api/projects/prj-nowhere/favourite").status_code == 404


def test_without_a_favourites_store_the_route_answers_409_and_the_list_still_serves() -> None:
    store = InMemoryProjectStore()
    store.save(Project("prj-1", "Nocturne", "AR", AT))
    app = Flask(__name__)
    app.register_blueprint(
        create_projects_blueprint(CreateProject(store), ListProjects(store), GetProject(store))
    )
    client = app.test_client()

    assert client.put("/api/projects/prj-1/favourite").status_code == 409
    listed = client.get("/api/projects").get_json()
    assert next(item for item in listed if item["project_id"] == "prj-1")["favourite"] is False


# --- Live mode: identity boundary and the access port ------------------------


class Verifier:
    def verify(self, token: str) -> Identity:
        if token not in {"alice", "bob"}:
            raise AuthenticationRequired("sign in again")
        return Identity(token, token + "@example.com")


class Access:
    """`ProjectAccess` and `ProjectFavourites` in one object, the way
    `FirestoreProjectAccess` implements both: the write authorizes through the
    same grants the read does."""

    def __init__(self) -> None:
        self.projects: dict[str, Project] = {
            "one": Project("one", "Nocturne", "AR", AT, "gs://p/one.jpg", "feature_film", None),
            "two": Project("two", "Otra", "AR", AT),
        }
        self.marked: dict[str, set[str]] = {}
        self.created: list[Project] = []

    def authorize(self, user_id: str, project_id: str, action: str) -> str:
        roles = {("alice", "one"): "producer", ("bob", "two"): "producer"}
        if not permits(roles.get((user_id, project_id), ""), action):
            raise AccessDenied("private details")
        return "organization-" + project_id

    def visible_project_ids(self, user_id: str) -> set[str]:
        return {"one"} if user_id == "alice" else {"two"}

    def get_project(self, project_id: str) -> Project:
        return self.projects[project_id]

    def create_project(self, user_id: str, organization_id: str, project: Project) -> None:
        self.created.append(project)
        self.projects[project.project_id] = project

    def create_organization(self, user_id: str, organization_id: str, name: str) -> None:
        pass

    def organizations(self, user_id: str) -> list[dict[str, str]]:
        return []

    def favourites(self, user_id: str) -> set[str]:
        return set(self.marked.get(user_id, set()))

    def add_favourite(self, user_id: str, project_id: str) -> None:
        self.authorize(user_id, project_id, "read")
        self.marked.setdefault(user_id, set()).add(project_id)

    def remove_favourite(self, user_id: str, project_id: str) -> None:
        self.marked.get(user_id, set()).discard(project_id)


@pytest.fixture
def live() -> tuple[FlaskClient, Access]:
    access = Access()
    store = InMemoryProjectStore()
    app = Flask(__name__)
    install_identity_boundary(app, Verifier(), access)
    app.register_blueprint(
        create_projects_blueprint(
            CreateProject(store), ListProjects(store), GetProject(store), access, access
        )
    )
    return app.test_client(), access


def _as(user: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + user}


def test_the_access_path_serves_the_same_shape_as_the_use_case_path(live) -> None:
    client, _ = live

    shown = client.get("/api/projects/one", headers=_as("alice")).get_json()

    assert set(shown) == PROJECT_FIELDS
    assert shown["poster_uri"] == "gs://p/one.jpg"
    assert shown["format"] == "feature_film"
    assert shown["status"] is None


def test_the_access_path_creates_a_project_carrying_the_three_fields(live) -> None:
    client, access = live

    response = client.post(
        "/api/projects",
        headers=_as("alice"),
        json={
            "title": "Nocturne",
            "jurisdiction_code": "AR",
            "organization_id": "org-one",
            "poster_uri": "gs://p/new.jpg",
            "format": "documentary",
            "status": "completed",
        },
    )

    assert response.status_code == 201
    assert access.created[0].format == "documentary"
    assert access.created[0].poster_uri == "gs://p/new.jpg"
    assert response.get_json()["status"] == "completed"


def test_a_favourite_is_marked_and_shows_on_the_list_for_that_user_only(live) -> None:
    client, _ = live

    assert client.put("/api/projects/one/favourite", headers=_as("alice")).status_code == 200

    alice = client.get("/api/projects", headers=_as("alice")).get_json()
    bob = client.get("/api/projects", headers=_as("bob")).get_json()
    assert alice[0]["favourite"] is True
    assert bob[0]["favourite"] is False


def test_a_user_cannot_favourite_a_project_they_cannot_see(live) -> None:
    """404, not 403: the answer is the same one reading it gives, so the route
    cannot be used to confirm that a project exists in another workspace."""
    client, access = live

    response = client.put("/api/projects/one/favourite", headers=_as("bob"))

    assert response.status_code == 404
    assert response.get_json() == {"error": "project not found"}
    assert access.favourites("bob") == set()


def test_favouriting_needs_an_identity_at_all(live) -> None:
    client, _ = live

    assert client.put("/api/projects/one/favourite").status_code == 401


def test_clearing_a_favourite_leaves_the_other_users_mark_alone(live) -> None:
    client, access = live
    client.put("/api/projects/one/favourite", headers=_as("alice"))
    client.put("/api/projects/two/favourite", headers=_as("bob"))

    client.delete("/api/projects/one/favourite", headers=_as("alice"))

    assert access.favourites("alice") == set()
    assert access.favourites("bob") == {"two"}
