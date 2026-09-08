"""Create-only screenplay JSON blobs with verified content digests."""

import hashlib
from typing import Any

from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.screenplay import MAX_DOCUMENT_BYTES, ContentReference


class GcsScreenplayContent:
    def __init__(self, client: Any, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def put(
        self, organization_id: str, project_id: str, content_id: str, data: bytes
    ) -> ContentReference:
        for value in (organization_id, project_id, content_id):
            if not value or value in {".", ".."} or "/" in value or "\\" in value:
                raise ValueError("invalid content namespace")
        key = f"organizations/{organization_id}/projects/{project_id}/drafts/{content_id}.json"
        try:
            self._client.bucket(self._bucket).blob(key).upload_from_string(
                data, content_type="application/json", if_generation_match=0
            )
        except Exception as exc:
            raise SourceUnavailable("screenplay storage unavailable") from exc
        return ContentReference(
            f"gs://{self._bucket}/{key}", hashlib.sha256(data).hexdigest(), len(data)
        )

    def get(self, reference: ContentReference) -> bytes:
        prefix = f"gs://{self._bucket}/organizations/"
        if not reference.uri.startswith(prefix):
            raise SourceUnavailable("screenplay content reference is invalid")
        key = reference.uri.removeprefix(f"gs://{self._bucket}/")
        try:
            data = (
                self._client.bucket(self._bucket)
                .blob(key)
                .download_as_bytes(start=0, end=MAX_DOCUMENT_BYTES)
            )
        except Exception as exc:
            raise SourceUnavailable("screenplay content unavailable") from exc
        if (
            len(data) != reference.size_bytes
            or hashlib.sha256(data).hexdigest() != reference.sha256
        ):
            raise SourceUnavailable("screenplay content failed integrity verification")
        return bytes(data)
