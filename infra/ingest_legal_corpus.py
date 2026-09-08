#!/usr/bin/env python3
"""Ingest the reviewed official-source manifest; default is an offline plan."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from infra.legal_source_content import SourceRejected, digest, download, extract  # noqa: E402

API = "https://discoveryengine.googleapis.com/v1/"
MANIFEST = Path(__file__).resolve().parent.parent / "docs/recovery/legal-sources-2026-09-06.json"


def encode(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def save(path: Path, value: Any) -> None:
    temporary = path.with_suffix(".pending")
    temporary.write_bytes(encode(value))
    temporary.replace(path)


def sources(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    result = [d for c in manifest["countries"] for d in c["documents"]]
    identifiers: set[str] = set()
    for source in result:
        identifier = source["id"]
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", identifier):
            raise SourceRejected("invalid stable document ID")
        if identifier in identifiers or source["kind"] != "statute":
            raise SourceRejected("duplicate document or non-normative source")
        identifiers.add(identifier)
        if source["jurisdiction"] not in {
            "argentina",
            "mexico",
            "spain",
            "colombia",
            "usa",
            "canada",
        }:
            raise SourceRejected("source is outside the six launch countries")
    return result


class Cloud:
    """No retries around import submission; callers retain the operation identity."""

    def __init__(self, project: str, bucket: str, datastore: str, location: str) -> None:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession

        session_factory: Any = AuthorizedSession
        from google.cloud import storage

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"], quota_project_id=project
        )
        self.session: Any = session_factory(credentials)
        self.session.headers["x-goog-user-project"] = project
        self.bucket = storage.Client(project=project, credentials=credentials).bucket(bucket)
        self.parent = (
            f"projects/{project}/locations/{location}/collections/default_collection/"
            f"dataStores/{datastore}"
        )

    def put(self, name: str, content: bytes, mime: str) -> str:
        from google.api_core.exceptions import PreconditionFailed

        blob = self.bucket.blob(name)
        try:
            blob.upload_from_string(content, content_type=mime, if_generation_match=0, timeout=60)
        except PreconditionFailed:
            existing = blob.download_as_bytes(timeout=60)
            if digest(existing) != digest(content):
                raise SourceRejected("immutable object collision") from None
        return f"gs://{self.bucket.name}/{name}"

    def request(self, method: str, resource: str, body: Any = None) -> dict[str, Any]:
        if not resource.startswith(self.parent + "/"):
            raise SourceRejected("operation or document escaped the configured data store")
        response = self.session.request(method, API + resource, json=body, timeout=60)
        if response.status_code not in (200, 201):
            raise SourceRejected(f"Discovery Engine HTTP {response.status_code}")
        result: dict[str, Any] = response.json()
        return result

    def submit(self, uri: str) -> str:
        response = self.request(
            "POST",
            self.parent + "/branches/0/documents:import",
            {
                "gcsSource": {"inputUris": [uri], "dataSchema": "document"},
                "reconciliationMode": "INCREMENTAL",
            },
        )
        name = response.get("name")
        if not isinstance(name, str) or not name.startswith(self.parent + "/"):
            raise SourceRejected("import returned no scoped operation identity")
        return name

    def operation(self, name: str) -> dict[str, Any]:
        return self.request("GET", name)

    def document(self, identifier: str) -> dict[str, Any]:
        return self.request("GET", self.parent + "/branches/0/documents/" + identifier)


def ingest(
    manifest: dict[str, Any],
    directory: Path,
    cloud: Any,
    http: httpx.Client,
    *,
    poll_seconds: float = 0,
) -> dict[str, Any]:
    """A state directory pins input and target. Failures retain evidence, never claim success."""
    documents = sources(manifest)
    directory.mkdir(parents=True, exist_ok=True)
    receipt_path = directory / "receipt.json"
    identity = {
        "manifest_sha256": digest(encode(manifest)),
        "target": cloud.parent,
        "bucket": cloud.bucket.name,
    }
    if receipt_path.exists():
        receipt: dict[str, Any] = json.loads(receipt_path.read_bytes())
        if receipt["identity"] != identity:
            raise SourceRejected("receipt belongs to another manifest or cloud target")
    else:
        receipt = {"identity": identity, "sources": {}, "status": "preparing"}
        save(receipt_path, receipt)
    lines = []
    for source in documents:
        identifier = source["id"]
        entry = receipt["sources"].get(identifier)
        original_path = directory / f"{identifier}.original"
        text_path = directory / f"{identifier}.txt"
        if entry is None or entry.get("status") == "gap":
            try:
                original, mime, final_url = download(http, source["url"])
                original_path.write_bytes(original)
                text, transform = extract(original, mime, source)
                text_path.write_bytes(text)
                entry = {
                    "status": "extracted",
                    "original_sha256": digest(original),
                    "text_sha256": digest(text),
                    "mime": mime,
                    "final_url": final_url,
                    "transform": transform,
                    "retrieved_at": datetime.now(UTC).isoformat(),
                }
                receipt["sources"][identifier] = entry
                save(receipt_path, receipt)
            except (SourceRejected, httpx.HTTPError) as exc:
                reason = (
                    str(exc)
                    if isinstance(exc, SourceRejected)
                    else "official source network failure"
                )
                receipt["sources"][identifier] = {"status": "gap", "reason": reason}
                receipt["status"] = "coverage_gap"
                save(receipt_path, receipt)
                continue
        original, text = original_path.read_bytes(), text_path.read_bytes()
        if digest(original) != entry["original_sha256"] or digest(text) != entry["text_sha256"]:
            raise SourceRejected("local receipt content integrity mismatch")
        prefix = f"{source['jurisdiction']}/official/{identifier}/{entry['original_sha256']}"
        original_uri = cloud.put(prefix + "/original", original, entry["mime"])
        text_uri = cloud.put(
            prefix + f"/{entry['text_sha256']}.txt", text, "text/plain; charset=utf-8"
        )
        metadata = {key: source[key] for key in ("jurisdiction", "subject", "title", "as_of")}
        metadata.update(
            source_url=source["url"],
            final_url=entry["final_url"],
            original_uri=original_uri,
            original_sha256=entry["original_sha256"],
            text_sha256=entry["text_sha256"],
            transformation=entry["transform"],
            retrieved_at=entry["retrieved_at"],
        )
        line = {
            "id": identifier,
            "structData": metadata,
            "content": {"mimeType": "text/plain", "uri": text_uri},
        }
        lines.append(line)
        entry.update(status="uploaded", document=line)
        save(receipt_path, receipt)
    if len(lines) != len(documents):
        receipt["status"] = "coverage_gap"
        save(receipt_path, receipt)
        return receipt
    batch = b"\n".join(encode(line) for line in lines) + b"\n"
    (directory / "documents.jsonl").write_bytes(batch)
    uri = cloud.put(f"_manifest/official/{digest(batch)}.jsonl", batch, "application/jsonl")
    if not receipt.get("operation"):
        if receipt["status"] == "submission_unknown":
            raise SourceRejected(
                "import submission outcome unknown; inspect operations before recovery"
            )
        receipt.update(status="submission_unknown", manifest_uri=uri)
        save(receipt_path, receipt)
        operation = cloud.submit(uri)
        receipt.update(status="importing", operation=operation)
        save(receipt_path, receipt)
    deadline = time.monotonic() + poll_seconds
    while True:
        operation_result = cloud.operation(receipt["operation"])
        receipt["operation_result"] = operation_result
        save(receipt_path, receipt)
        if operation_result.get("done") or time.monotonic() >= deadline:
            break
        time.sleep(min(5, max(0, deadline - time.monotonic())))
    if not operation_result.get("done"):
        return receipt
    response = operation_result.get("response", {})
    if (
        operation_result.get("error")
        or response.get("errorSamples")
        or int(operation_result.get("metadata", {}).get("failureCount", 0)) > 0
    ):
        receipt["status"] = "import_failed"
    else:
        receipt["status"] = "readback_pending"
        save(receipt_path, receipt)
        for expected in lines:
            actual = cloud.document(expected["id"])
            if actual.get("content") != expected["content"] or any(
                actual.get("structData", {}).get(key) != value
                for key, value in expected["structData"].items()
            ):
                raise SourceRejected("imported document readback mismatch")
        receipt.update(
            status="imported_readback_verified",
            verified_at=datetime.now(UTC).isoformat(),
            evaluation_status="unverified",
        )
    save(receipt_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--project")
    parser.add_argument("--bucket")
    parser.add_argument("--datastore")
    parser.add_argument("--location", default="global", choices=("global", "us", "eu"))
    parser.add_argument("--poll-seconds", type=float, default=45)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_bytes())
    documents = sources(manifest)
    if not args.apply:
        print(
            json.dumps(
                {
                    "mode": "dry-run",
                    "documents": documents,
                    "excluded_sources": [
                        s for c in manifest["countries"] for s in c.get("excluded_sources", [])
                    ],
                },
                indent=2,
            )
        )
        return 0
    if not all((args.state_dir, args.project, args.bucket, args.datastore)):
        parser.error("--apply requires --state-dir, --project, --bucket and --datastore")
    for value in (args.project, args.bucket, args.datastore):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", value):
            parser.error("cloud resource identifiers must be plain names")
    if not 0 <= args.poll_seconds <= 55:
        parser.error("--poll-seconds must be finite and between 0 and 55")
    try:
        cloud = Cloud(args.project, args.bucket, args.datastore, args.location)
        with httpx.Client(timeout=httpx.Timeout(45, connect=10)) as http:
            receipt = ingest(manifest, args.state_dir, cloud, http, poll_seconds=args.poll_seconds)
        print(
            json.dumps(
                {"status": receipt["status"], "receipt": str(args.state_dir / "receipt.json")}
            )
        )
        return 0 if receipt["status"] == "imported_readback_verified" else 1
    except Exception:
        print(
            "Legal ingestion did not verify successfully; inspect the local receipt.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
