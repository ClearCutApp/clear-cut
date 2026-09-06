"""Writes an uploaded screenplay to Cloud Storage (`application/ports.py`,
`ScriptStorage`).

The bytes cross a boundary here rather than being handed straight to
`ScriptIngestion.parse`, because Document AI reads the object from the bucket
rather than from this process. The `gs://` URI this returns is what the
producer's next call carries.

The bucket name arrives as a constructor argument. `composition.py` reads
`SCRIPTS_INTAKE_BUCKET` and passes the value in; no adapter reads the
environment itself, so a test can point this one at any bucket and the
environment contract has exactly one place to check (AGENT.md Section 2
rule 4).

The client is typed against a narrow local `Protocol` rather than the
concrete `google.cloud.storage.Client`, which resolves credentials at
construction -- the same reason `document_ai.py` and `lore_store.py` declare
their own. A real `Client` satisfies it structurally, so the composition root
wires the real instance unchanged.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Protocol

from clearcut.domain.errors import SourceUnavailable

# Every screenplay this service accepts is a PDF: `ScriptFile.content_type`
# in docs/api/openapi.yaml is an enum with one member, and Document AI's
# processor is configured for that type. A parameter here would be config for
# a value that has never varied (AGENT.md Section 4).
_CONTENT_TYPE = "application/pdf"


class ScriptUploadFailed(SourceUnavailable):
    """Cloud Storage refused or could not complete the write."""

    def __init__(self, bucket: str, blob_name: str, cause: Exception) -> None:
        super().__init__(f"failed to upload {blob_name!r} to bucket {bucket!r}: {cause}")
        self.bucket = bucket
        self.blob_name = blob_name


class _Blob(Protocol):
    """The one `google.cloud.storage.Blob` method this adapter calls."""

    def upload_from_string(self, data: bytes, content_type: str) -> None: ...


class _Bucket(Protocol):
    """The one `google.cloud.storage.Bucket` method this adapter calls."""

    def blob(self, blob_name: str) -> _Blob: ...


class _StorageClient(Protocol):
    """The one `google.cloud.storage.Client` method this adapter calls."""

    def bucket(self, bucket_name: str) -> _Bucket: ...


class GcsScriptStorage:
    """Implements `ScriptStorage` over a Cloud Storage bucket."""

    def __init__(self, client: _StorageClient, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def store(self, project_id: str, filename: str, content: bytes) -> str:
        blob_name = f"{_checked_project_id(project_id)}/{_basename(filename)}"
        try:
            blob = self._client.bucket(self._bucket).blob(blob_name)
            blob.upload_from_string(content, content_type=_CONTENT_TYPE)
        except Exception as exc:
            # Broader than `document_ai.py`'s `except GoogleAPIError` on
            # purpose: one upload can raise out of three unrelated
            # hierarchies -- `google.api_core.exceptions` for a refused
            # request, `google.auth.exceptions` for a credential that will
            # not refresh, and `google.resumable_media` for a transfer that
            # breaks mid-stream. None of them share a base, and the two this
            # adapter did not name would reach a Flask route as an untyped
            # 500 (D23, tests/unit/test_error_boundaries.py).
            raise ScriptUploadFailed(self._bucket, blob_name, exc) from exc
        return f"gs://{self._bucket}/{blob_name}"


def _checked_project_id(project_id: str) -> str:
    if not project_id.strip():
        raise ValueError("project_id must not be blank")
    return project_id


def _basename(filename: str) -> str:
    """The last path segment of `filename`, with nothing above it.

    The name comes from a producer's upload form, and the object key is the
    only thing keeping one project's scripts out of another's prefix. A name
    like `../prj-other/draft.pdf` would otherwise write across that line.
    """
    name = PurePosixPath(filename.strip()).name
    if not name or name in {".", ".."}:
        raise ValueError(f"filename has no usable name: {filename!r}")
    return name
