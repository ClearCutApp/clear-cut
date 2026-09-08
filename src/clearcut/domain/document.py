"""Immutable project files retain provenance independently of display filenames."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectDocument:
    file_id: str
    organization_id: str
    project_id: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    storage_uri: str
    kind: str
    created_by: str
    created_at: str
    revision_id: str = ""


class InvalidDocument(ValueError):
    """A file cannot be imported or exported in the requested format."""
