"""Tests for `clearcut.domain.project` (CP-061)."""

import dataclasses

import pytest

from clearcut.domain.errors import UnknownJurisdiction
from clearcut.domain.project import Project


def _project(
    project_id: str = "proj-1",
    title: str = "Nocturne",
    jurisdiction_code: str = "AR",
    created_at: str = "2026-09-01T00:00:00Z",
) -> Project:
    return Project(
        project_id=project_id,
        title=title,
        jurisdiction_code=jurisdiction_code,
        created_at=created_at,
    )


def test_project_keeps_the_four_values_it_was_given():
    project = _project()

    assert project.project_id == "proj-1"
    assert project.title == "Nocturne"
    assert project.jurisdiction_code == "AR"
    assert project.created_at == "2026-09-01T00:00:00Z"


def test_two_projects_with_equal_fields_compare_equal():
    assert _project() == _project()


def test_project_is_frozen():
    project = _project()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(project, "title", "Different Title")


@pytest.mark.parametrize("blank_project_id", ["", "   "])
def test_blank_project_id_raises_value_error(blank_project_id):
    with pytest.raises(ValueError, match="project_id"):
        _project(project_id=blank_project_id)


@pytest.mark.parametrize("blank_title", ["", "   "])
def test_blank_title_raises_value_error(blank_title):
    with pytest.raises(ValueError, match="title"):
        _project(title=blank_title)


def test_unknown_jurisdiction_code_raises_the_error_jurisdiction_for_raises():
    with pytest.raises(UnknownJurisdiction):
        _project(jurisdiction_code="ZZ")
