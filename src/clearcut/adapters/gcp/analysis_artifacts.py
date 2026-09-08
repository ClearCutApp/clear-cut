"""Immutable, bounded and integrity-checked analysis artifacts in private GCS."""

import hashlib
import json
from typing import Any
from uuid import uuid4

from clearcut.application.analysis_documents import canonical
from clearcut.domain.errors import SourceUnavailable
from clearcut.domain.screenplay import ContentReference

MAX_ARTIFACT_BYTES = 64 * 1024 * 1024


class GcsAnalysisArtifacts:
    def __init__(self, client: Any, bucket: str) -> None:
        self.client, self.bucket = client, bucket

    def put(
        self,
        organization_id: str,
        project_id: str,
        analysis_id: str,
        kind: str,
        value: dict[str, Any],
    ) -> ContentReference:
        return self.put_bytes(
            organization_id, project_id, analysis_id, kind, canonical(value), "application/json"
        )

    def put_bytes(
        self,
        organization_id: str,
        project_id: str,
        analysis_id: str,
        kind: str,
        content: bytes,
        content_type: str,
    ) -> ContentReference:
        for value in (organization_id, project_id, analysis_id, kind):
            if not value or value in {".", ".."} or any(char in value for char in "/\\"):
                raise ValueError("invalid analysis artifact namespace")
        if len(content) > MAX_ARTIFACT_BYTES:
            raise ValueError("analysis artifact exceeds the storage limit")
        key = (
            f"organizations/{organization_id}/projects/{project_id}/"
            f"analyses/{analysis_id}/{kind}/{uuid4().hex}"
        )
        try:
            self.client.bucket(self.bucket).blob(key).upload_from_string(
                content,
                content_type=content_type,
                if_generation_match=0,
                timeout=60,
                retry=None,
            )
        except Exception as exc:
            raise SourceUnavailable("analysis artifact storage unavailable") from exc
        return ContentReference(
            f"gs://{self.bucket}/{key}", hashlib.sha256(content).hexdigest(), len(content)
        )

    def get_bytes(self, reference: ContentReference) -> bytes:
        prefix = f"gs://{self.bucket}/organizations/"
        if (
            not reference.uri.startswith(prefix)
            or not 0 <= reference.size_bytes <= MAX_ARTIFACT_BYTES
        ):
            raise SourceUnavailable("invalid analysis artifact reference")
        key = reference.uri.removeprefix(f"gs://{self.bucket}/")
        if "/analyses/" not in key or any(part in {".", ".."} for part in key.split("/")):
            raise SourceUnavailable("invalid analysis artifact reference")
        try:
            data = bytes(
                self.client.bucket(self.bucket)
                .blob(key)
                .download_as_bytes(
                    start=0,
                    end=reference.size_bytes,
                    timeout=60,
                    retry=None,
                )
            )
        except Exception as exc:
            raise SourceUnavailable("analysis artifact unavailable") from exc
        if (
            len(data) != reference.size_bytes
            or hashlib.sha256(data).hexdigest() != reference.sha256
        ):
            raise SourceUnavailable("analysis artifact integrity check failed")
        return data

    def get(self, reference: ContentReference) -> dict[str, Any]:
        try:
            value = json.loads(self.get_bytes(reference))
        except (ValueError, UnicodeError) as exc:
            raise SourceUnavailable("invalid analysis artifact") from exc
        if not isinstance(value, dict):
            raise SourceUnavailable("invalid analysis artifact")
        return value
