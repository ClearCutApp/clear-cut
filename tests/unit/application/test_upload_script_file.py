"""Unit tests for `UploadScriptFile` (docs/api/openapi.yaml,
`POST /api/projects/{project_id}/script-files`).

The happy path uses the shared `FakeScriptStorage`, which records what it was
handed and answers a `gs://` URI shaped like the real one. The two failure
paths need a fake that raises, so this file writes its own -- and raises a
plain `SourceUnavailable` rather than the adapter's `ScriptUploadFailed`,
because `application/` and the tests around it never import
`clearcut.adapters` (AGENT.md Section 2 rule 2,
tests/unit/test_layer_boundaries.py).

Hand-written fakes only, no `unittest.mock`, no network (AGENT.md Section 5).
"""

import pytest

from clearcut.application.ports import ScriptStorage
from clearcut.application.upload_script_file import StoredScriptFile, UploadScriptFile
from clearcut.domain.errors import SourceUnavailable
from tests.unit.fakes import FakeScriptStorage

_PDF_BYTES = b"%PDF-1.7 el-ultimo-verano"


class _FailingScriptStorage:
    """Refuses every write, the way the bucket does when the object cannot be
    written. Records the attempt so a test can prove the port was reached."""

    def __init__(self) -> None:
        self.attempts: list[tuple[str, str, bytes]] = []

    def store(self, project_id: str, filename: str, content: bytes) -> str:
        self.attempts.append((project_id, filename, content))
        raise SourceUnavailable("bucket refused the write")


_conforms: ScriptStorage = _FailingScriptStorage()


def test_failing_script_storage_satisfies_the_scriptstorage_port() -> None:
    assert isinstance(_conforms, ScriptStorage)


def test_execute_returns_the_uri_the_storage_answered_with() -> None:
    storage = FakeScriptStorage()
    use_case = UploadScriptFile(storage)

    stored = use_case.execute("prj-4f2a", "el-ultimo-verano-v2.pdf", _PDF_BYTES)

    assert stored == StoredScriptFile(
        gcs_uri="gs://clearcut-scripts/prj-4f2a/el-ultimo-verano-v2.pdf",
        filename="el-ultimo-verano-v2.pdf",
        size_bytes=len(_PDF_BYTES),
    )


def test_execute_writes_the_bytes_it_was_given_through_the_port() -> None:
    storage = FakeScriptStorage()

    UploadScriptFile(storage).execute("prj-4f2a", "el-ultimo-verano-v2.pdf", _PDF_BYTES)

    assert storage.stored == [("prj-4f2a", "el-ultimo-verano-v2.pdf", _PDF_BYTES)]


def test_execute_rejects_empty_content_without_touching_the_storage() -> None:
    """A zero-byte upload is a failed upload: storing it would hand Document
    AI an object with nothing to parse, failing a queued job instead of the
    request the producer is still watching."""
    storage = FakeScriptStorage()
    use_case = UploadScriptFile(storage)

    with pytest.raises(ValueError, match="content must not be empty"):
        use_case.execute("prj-4f2a", "el-ultimo-verano-v2.pdf", b"")

    assert storage.stored == []


def test_execute_propagates_a_storage_failure_unchanged() -> None:
    storage = _FailingScriptStorage()
    use_case = UploadScriptFile(storage)

    with pytest.raises(SourceUnavailable, match="bucket refused the write"):
        use_case.execute("prj-4f2a", "el-ultimo-verano-v2.pdf", _PDF_BYTES)

    assert storage.attempts == [("prj-4f2a", "el-ultimo-verano-v2.pdf", _PDF_BYTES)]


def test_execute_accepts_a_filename_the_use_case_does_not_inspect() -> None:
    """File-type validation is the route's job: the contract answers 400 for a
    non-PDF, which is a rule about the request shape rather than about
    scripts."""
    storage = FakeScriptStorage()

    stored = UploadScriptFile(storage).execute("prj-4f2a", "notes.txt", b"not a pdf")

    assert stored.filename == "notes.txt"
    assert stored.gcs_uri == "gs://clearcut-scripts/prj-4f2a/notes.txt"
