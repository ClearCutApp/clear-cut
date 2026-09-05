"""Unit tests for `GcsScriptStorage` (`application/ports.py`, ScriptStorage).

The real `google.cloud.storage.Client` resolves credentials at construction
and opens an HTTPS connection on the first call, so these tests fake the
client boundary directly (AGENT.md Section 5). No `unittest.mock`, no
network, no bucket.
"""

from __future__ import annotations

import pytest

from clearcut.adapters.gcp.storage import GcsScriptStorage, ScriptUploadFailed
from clearcut.application.ports import ScriptStorage

_PDF = b"%PDF-1.7\nel ultimo verano\n"


class FakeBlob:
    """Records the one upload it is asked to perform."""

    def __init__(self, name: str, bucket: FakeBucket) -> None:
        self.name = name
        self._bucket = bucket

    def upload_from_string(self, data: bytes, content_type: str) -> None:
        self._bucket.uploads.append((self.name, data, content_type))


class FakeBucket:
    def __init__(self, name: str) -> None:
        self.name = name
        self.uploads: list[tuple[str, bytes, str]] = []

    def blob(self, blob_name: str) -> FakeBlob:
        return FakeBlob(blob_name, self)


class FakeStorageClient:
    """Hands back one `FakeBucket` per name, remembering which it was asked for."""

    def __init__(self) -> None:
        self.buckets: dict[str, FakeBucket] = {}
        self.requested: list[str] = []

    def bucket(self, bucket_name: str) -> FakeBucket:
        self.requested.append(bucket_name)
        return self.buckets.setdefault(bucket_name, FakeBucket(bucket_name))


class ExplodingStorageClient:
    """Raises a real `google-api-core` error, the shape the SDK actually
    raises, rather than a stand-in a narrow `except` clause would miss."""

    def bucket(self, bucket_name: str) -> FakeBucket:
        from google.api_core.exceptions import Forbidden

        raise Forbidden("simulated permission failure")  # type: ignore[no-untyped-call]


class ExplodingBlob:
    def upload_from_string(self, data: bytes, content_type: str) -> None:
        from google.auth.exceptions import RefreshError

        raise RefreshError("simulated credential failure")  # type: ignore[no-untyped-call]


class ExplodingUploadBucket:
    def blob(self, blob_name: str) -> ExplodingBlob:
        return ExplodingBlob()


class ExplodingUploadClient:
    def bucket(self, bucket_name: str) -> ExplodingUploadBucket:
        return ExplodingUploadBucket()


def test_adapter_satisfies_the_scriptstorage_port() -> None:
    adapter = GcsScriptStorage(FakeStorageClient(), bucket="clearcut-scripts")
    checked: ScriptStorage = adapter
    assert isinstance(checked, ScriptStorage)


def test_store_returns_the_gs_uri_document_ai_reads_back() -> None:
    """`ScriptIngestion.parse` takes this string and Document AI reads the
    object from the bucket, so the return value is the whole point of the
    port: the bytes are not passed between the two in memory."""
    adapter = GcsScriptStorage(FakeStorageClient(), bucket="clearcut-scripts")

    uri = adapter.store("prj-4f2a", "el-ultimo-verano-v2.pdf", _PDF)

    assert uri == "gs://clearcut-scripts/prj-4f2a/el-ultimo-verano-v2.pdf"


def test_store_writes_the_bytes_under_the_projects_own_prefix() -> None:
    client = FakeStorageClient()
    adapter = GcsScriptStorage(client, bucket="clearcut-scripts")

    adapter.store("prj-4f2a", "draft.pdf", _PDF)

    assert client.requested == ["clearcut-scripts"]
    assert client.buckets["clearcut-scripts"].uploads == [
        ("prj-4f2a/draft.pdf", _PDF, "application/pdf")
    ]


def test_store_takes_the_bucket_it_was_constructed_with_never_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The composition root reads `SCRIPTS_INTAKE_BUCKET` and passes the
    value in (AGENT.md Section 2 rule 4). An adapter that read it itself
    would make the bucket unswappable in a test and invisible to the
    environment contract."""
    monkeypatch.setenv("SCRIPTS_INTAKE_BUCKET", "some-other-bucket")
    client = FakeStorageClient()

    uri = GcsScriptStorage(client, bucket="clearcut-scripts").store("prj-1", "a.pdf", _PDF)

    assert uri.startswith("gs://clearcut-scripts/")
    assert client.requested == ["clearcut-scripts"]


def test_store_keeps_only_the_basename_of_a_filename_carrying_a_path() -> None:
    """The filename comes from a producer's upload form. A name like
    `../prj-other/draft.pdf` would otherwise write into another project's
    prefix, and the object key is the only thing separating them."""
    client = FakeStorageClient()
    adapter = GcsScriptStorage(client, bucket="clearcut-scripts")

    uri = adapter.store("prj-4f2a", "../prj-other/draft.pdf", _PDF)

    assert uri == "gs://clearcut-scripts/prj-4f2a/draft.pdf"
    assert client.buckets["clearcut-scripts"].uploads[0][0] == "prj-4f2a/draft.pdf"


@pytest.mark.parametrize("filename", ["", "   ", "/", "..", "../.."])
def test_a_filename_with_no_basename_left_is_refused(filename: str) -> None:
    adapter = GcsScriptStorage(FakeStorageClient(), bucket="clearcut-scripts")

    with pytest.raises(ValueError):
        adapter.store("prj-4f2a", filename, _PDF)


def test_a_blank_project_id_is_refused() -> None:
    """A blank project writes to `gs://bucket//draft.pdf`, an object nothing
    can find again and that belongs to no project."""
    adapter = GcsScriptStorage(FakeStorageClient(), bucket="clearcut-scripts")

    with pytest.raises(ValueError):
        adapter.store("  ", "draft.pdf", _PDF)


def test_a_bucket_lookup_failure_becomes_a_domain_error() -> None:
    adapter = GcsScriptStorage(ExplodingStorageClient(), bucket="clearcut-scripts")

    with pytest.raises(ScriptUploadFailed) as excinfo:
        adapter.store("prj-4f2a", "draft.pdf", _PDF)

    assert "clearcut-scripts" in str(excinfo.value)


def test_a_credential_failure_during_upload_becomes_a_domain_error() -> None:
    """`google.auth` errors do not subclass `GoogleAPIError`, so an adapter
    that caught only the API hierarchy would let a stale credential reach the
    route as a 500 with a stack trace."""
    adapter = GcsScriptStorage(ExplodingUploadClient(), bucket="clearcut-scripts")

    with pytest.raises(ScriptUploadFailed):
        adapter.store("prj-4f2a", "draft.pdf", _PDF)
