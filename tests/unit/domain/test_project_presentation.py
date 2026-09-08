"""The three optional presentation fields on `Project`.

They live in their own suite rather than in `test_project.py` because they
answer a different question: `test_project.py` asks what a project is, and
this asks what it is allowed to say about itself. `None` is the answer for
every one of them until somebody chooses otherwise, and nothing here may
invent a default -- a project that reads back as a feature film because that
is the common case is a project claiming a format nobody gave it.
"""

import pytest

from clearcut.domain.project import PROJECT_FORMATS, PROJECT_STATUSES, Project


def _project(**overrides: str | None) -> Project:
    fields: dict[str, str | None] = dict(
        project_id="prj-1",
        title="Nocturne",
        jurisdiction_code="AR",
        created_at="2026-09-01T00:00:00Z",
    )
    fields.update(overrides)
    return Project(**fields)  # type: ignore[arg-type]


def test_a_project_created_without_them_has_all_three_unset():
    project = _project()

    assert project.poster_uri is None
    assert project.format is None
    assert project.status is None


@pytest.mark.parametrize("value", sorted(PROJECT_FORMATS))
def test_every_listed_format_is_accepted(value):
    assert _project(format=value).format == value


@pytest.mark.parametrize("value", sorted(PROJECT_STATUSES))
def test_every_listed_status_is_accepted(value):
    assert _project(status=value).status == value


def test_an_unlisted_format_is_refused_naming_the_value_and_the_set():
    with pytest.raises(ValueError) as excinfo:
        _project(format="feature-film")

    assert "feature-film" in str(excinfo.value)
    assert "feature_film" in str(excinfo.value)


def test_an_unlisted_status_is_refused():
    with pytest.raises(ValueError, match="status"):
        _project(status="shooting")


def test_none_stays_valid_for_both_closed_sets():
    """The guard rejects a wrong value, never an absent one: a project with no
    declared format is the ordinary case, not a malformed record."""
    project = _project(format=None, status=None)

    assert (project.format, project.status) == (None, None)


def test_a_poster_uri_is_kept_exactly_as_given():
    """No validation of its own. Where a poster lives is the deployment's
    business, and a domain that insisted on `gs://` would refuse an https
    URL the frontend can already draw."""
    project = _project(poster_uri="https://cdn.example.test/prj-1.jpg")

    assert project.poster_uri == "https://cdn.example.test/prj-1.jpg"


def test_the_two_sets_do_not_overlap():
    """A value valid for both fields would let a misspelled `format` pass as a
    status, which is the exact confusion the closed sets exist to catch."""
    assert not PROJECT_FORMATS & PROJECT_STATUSES


def test_two_projects_differing_only_in_format_are_not_equal():
    assert _project(format="documentary") != _project(format="short")
