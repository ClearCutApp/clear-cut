#!/usr/bin/env python3
"""Map GCS object URIs into the JSONL metadata manifest that feeds Vertex AI
Search (docs/plan/infrastructure.md Section 5).

Reads one GCS object URI per line on stdin and writes one manifest line per
document to stdout: ``{"id": ..., "structData": {"jurisdiction": ...},
"content": {"mimeType": ..., "uri": ...}}``. Makes no network call -- the
step that lists the bucket (``gcloud storage ls``, piped in) stays separate
from the mapping done here, which is what keeps the mapping unit-testable.

Usage:
    gcloud storage ls "gs://clearcut-legal-corpus/**" | infra/build_manifest.py
"""

from __future__ import annotations

import json
import mimetypes
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

# Run standalone (`infra/build_manifest.py`, no PYTHONPATH set), so this adds
# the repo's src/ to sys.path the same way pyproject.toml's pytest pythonpath
# does for tests, before importing the package it needs.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from clearcut.domain.jurisdiction import JURISDICTIONS  # noqa: E402


class UnmatchedJurisdictionPrefix(Exception):
    """Raised when a URI's object path matches no known `corpus_prefix`.

    Emitting a line with a blank or guessed jurisdiction instead would be
    exactly the failure this manifest exists to prevent: a blank jurisdiction
    makes a filtered query return every jurisdiction's documents.
    """

    def __init__(self, uri: str) -> None:
        super().__init__(f"no jurisdiction prefix matches {uri!r}")
        self.uri = uri


def _object_path(uri: str) -> str:
    """Strip the ``gs://<bucket>/`` prefix off a GCS object URI."""
    _, _, rest = uri.partition("://")
    _, _, path = rest.partition("/")
    return path


def _jurisdiction_for(uri: str) -> str:
    """Match a URI's object path against the ten `corpus_prefix` values.

    `corpus_prefix` values live in `clearcut.domain.jurisdiction` (CP-002),
    so this script reuses them rather than retyping the ten prefixes.
    """
    path = _object_path(uri)
    for jurisdiction in JURISDICTIONS:
        if path.startswith(jurisdiction.corpus_prefix):
            return jurisdiction.corpus_prefix.rstrip("/")
    raise UnmatchedJurisdictionPrefix(uri)


def _manifest_id(uri: str) -> str:
    """Derive a stable manifest id from a URI's object path."""
    path, _, _ = _object_path(uri).rpartition(".")
    return (path or _object_path(uri)).replace("/", "-")


def build_manifest_line(uri: str) -> dict[str, object]:
    """Map one GCS object URI to one JSONL manifest entry."""
    jurisdiction = _jurisdiction_for(uri)
    mime_type, _ = mimetypes.guess_type(uri)
    return {
        "id": _manifest_id(uri),
        "structData": {"jurisdiction": jurisdiction},
        "content": {
            "mimeType": mime_type or "application/octet-stream",
            "uri": uri,
        },
    }


def build_manifest_lines(uris: Iterable[str]) -> Iterator[dict[str, object]]:
    for uri in uris:
        yield build_manifest_line(uri)


def main() -> int:
    uris = [line.strip() for line in sys.stdin if line.strip()]
    try:
        lines = list(build_manifest_lines(uris))
    except UnmatchedJurisdictionPrefix as exc:
        print(f"build_manifest.py: {exc}", file=sys.stderr)
        return 1
    for entry in lines:
        print(json.dumps(entry))
    return 0


if __name__ == "__main__":
    sys.exit(main())
