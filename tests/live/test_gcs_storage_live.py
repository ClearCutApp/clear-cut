"""`GcsScriptStorage` against a real Cloud Storage bucket.

The proof is what the server assigns and this process could not have known.
A generation number is minted by Cloud Storage on write, and `crc32c` is the
checksum it computed over the bytes it received -- neither exists until the
object does. Asserting that the upload raised nothing would hold against the
hand-written fake in `tests/unit/adapters/test_gcs_storage.py`, which is why
it is not the assertion here.

`SCRIPTS_INTAKE_BUCKET` names the bucket. The adapter takes it as a
constructor argument (`composition.py` reads it), so this test reads the
variable itself rather than expecting the adapter to.
"""

import base64
import uuid

import pytest
from google.cloud import storage

from clearcut.adapters.gcp.storage import GcsScriptStorage, ScriptUploadFailed
from tests.live.conftest import env, requires, scratch_id

_CREDENTIALS = ("GOOGLE_CLOUD_PROJECT", "SCRIPTS_INTAKE_BUCKET")

_PDF = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< >>\n%%EOF\n"


def _client() -> storage.Client:
    return storage.Client(project=env("GOOGLE_CLOUD_PROJECT"))


@pytest.mark.live
@requires(*_CREDENTIALS)
def test_an_uploaded_script_carries_the_generation_cloud_storage_assigned_it() -> None:
    bucket_name = env("SCRIPTS_INTAKE_BUCKET")
    client = _client()
    project_id = scratch_id("live-prj")
    filename = f"{uuid.uuid4().hex[:12]}.pdf"

    uri = GcsScriptStorage(client, bucket=bucket_name).store(project_id, filename, _PDF)

    assert uri == f"gs://{bucket_name}/{project_id}/{filename}"
    blob = client.bucket(bucket_name).get_blob(f"{project_id}/{filename}")
    assert blob is not None, "the object the adapter reported writing does not exist"
    try:
        assert blob.generation > 0
        assert blob.size == len(_PDF)
        assert blob.content_type == "application/pdf"
        # The checksum Cloud Storage computed over the bytes it received,
        # base64 of a big-endian CRC32C. Comparing it to a locally computed
        # one proves the transfer, not only the metadata.
        assert base64.b64decode(blob.crc32c) == _crc32c(_PDF)
    finally:
        blob.delete()


@pytest.mark.live
@requires(*_CREDENTIALS)
def test_a_bucket_that_does_not_exist_raises_the_domain_error() -> None:
    """A real 404 out of the Cloud Storage API, translated at the boundary.
    The bucket name is a fresh uuid, so it cannot exist."""
    storage_adapter = GcsScriptStorage(_client(), bucket=f"clearcut-absent-{uuid.uuid4().hex}")

    with pytest.raises(ScriptUploadFailed):
        storage_adapter.store(scratch_id("live-prj"), "draft.pdf", _PDF)


def _crc32c(data: bytes) -> bytes:
    """CRC32C of `data` as four big-endian bytes, through the same library
    the Cloud Storage SDK uses to verify its own uploads."""
    import google_crc32c

    checksum = google_crc32c.Checksum()  # type: ignore[no-untyped-call]
    checksum.update(data)  # type: ignore[no-untyped-call]
    digest: bytes = checksum.digest()  # type: ignore[no-untyped-call]
    return digest
