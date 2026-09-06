"""Stores an uploaded screenplay and reports what was written
(docs/api/openapi.yaml, `POST /api/projects/{project_id}/script-files`).

Nothing is parsed here. The route answers 201 with the `gs://` URI, and the
producer's next call passes that URI to `POST /api/projects/{project_id}/scripts`
to queue the analysis, so re-running an analysis over the same upload costs no
second transfer.

The one rule this use case holds is that empty bytes are not a script. A
zero-byte object would be written, returned as a URI, and then handed to
Document AI, which has nothing to parse and fails at the far end of a queued
job rather than at the upload the producer is still watching.

What the file *is* stays outside: the contract answers 400 for anything that
is not a PDF, which is a rule about the request shape rather than about
scripts, and `adapters/http/routes.py` owns it. `GcsScriptStorage` already
pins `application/pdf` on the object it writes.
"""

from dataclasses import dataclass

from clearcut.application.ports import ScriptStorage


@dataclass(frozen=True)
class StoredScriptFile:
    """One stored screenplay, the three fields the `ScriptFile` response
    carries beyond its fixed `content_type`.

    `size_bytes` is the length of what this use case handed the port, not a
    size read back from the bucket: the read that would confirm it is a
    second network call to learn something the caller already knows.
    """

    gcs_uri: str
    filename: str
    size_bytes: int


class UploadScriptFile:
    """`UploadScriptFile(storage)` (docs/plan/sdd.md Section 4.1)."""

    def __init__(self, storage: ScriptStorage) -> None:
        self._storage = storage

    def execute(self, project_id: str, filename: str, content: bytes) -> StoredScriptFile:
        """Write `content` and answer with the URI the port returned.

        Raises `ValueError` for empty `content`, before the port is touched.
        A `SourceUnavailable` from the port propagates unchanged: an upload
        that did not land is a failed request, and there is nothing here that
        could stand in for the bytes.
        """
        if not content:
            raise ValueError("content must not be empty")
        gcs_uri = self._storage.store(project_id, filename, content)
        return StoredScriptFile(gcs_uri=gcs_uri, filename=filename, size_bytes=len(content))
