"""Immutable same-project GCS backup, pinned source generations and resumable receipts."""

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from google.api_core.exceptions import NotFound, PreconditionFailed

from infra.migration_snapshot import canonical, digest_file, rows, verify

MAX_ORIGINAL_BYTES = 512 * 1024 * 1024


def receipt_write(path: Path, value: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, delete=False) as output:
        output.write(canonical(value))
        output.flush()
        os.fsync(output.fileno())
        temporary = output.name
    os.replace(temporary, path)


class MissingSourceGeneration(Exception):
    pass


def observe_source(blob: Any) -> None:
    try:
        blob.reload(timeout=30, retry=None)
    except NotFound:
        raise MissingSourceGeneration from None


def download_source(blob: Any, path: Path, generation: int) -> None:
    try:
        blob.download_to_filename(
            str(path), if_generation_match=generation, timeout=120, retry=None
        )
    except NotFound:
        raise MissingSourceGeneration from None


def verify_blob(blob: Any, path: Path, digest: str, size: int) -> None:
    blob.reload(timeout=30, retry=None)
    if int(blob.size) != size:
        raise ValueError("backup object size mismatch")
    with tempfile.NamedTemporaryFile(dir=path.parent) as target:
        blob.download_to_filename(
            target.name, if_generation_match=int(blob.generation), timeout=120, retry=None
        )
        if digest_file(Path(target.name)) != (digest, size):
            raise ValueError("backup object byte hash mismatch")


def put_immutable(bucket: Any, object_name: str, path: Path) -> dict[str, Any]:
    digest, size = digest_file(path)
    blob = bucket.blob(object_name)
    blob.metadata = {"sha256": digest}
    try:
        blob.upload_from_filename(str(path), if_generation_match=0, timeout=120, retry=None)
    except PreconditionFailed:
        pass
    verify_blob(blob, path, digest, size)
    return {
        "uri": f"gs://{bucket.name}/{object_name}",
        "generation": str(blob.generation),
        "sha256": digest,
        "size_bytes": size,
    }


def stage(
    client: Any,
    directory: Path,
    *,
    project_number: str,
    intake_bucket: str,
    backup_bucket: str,
    run_id: str,
) -> dict[str, Any]:
    report = verify(directory)
    destination = client.bucket(backup_bucket)
    source = client.bucket(intake_bucket)
    destination.reload(timeout=30, retry=None)
    source.reload(timeout=30, retry=None)
    if (
        str(destination.project_number) != project_number
        or str(source.project_number) != project_number
    ):
        raise ValueError("source and backup buckets must belong to the selected GCP project")
    if destination.iam_configuration.public_access_prevention != "enforced":
        raise ValueError("backup bucket must enforce public access prevention")
    identity = {
        "run_id": run_id,
        "source_manifest_sha256": report["manifest_sha256"],
        "project_number": project_number,
        "intake_bucket": intake_bucket,
        "backup_bucket": backup_bucket,
    }
    path = directory / "object-receipt.json"
    if path.exists():
        receipt = json.loads(path.read_bytes())
        if receipt.get("identity") != identity:
            raise ValueError("object receipt belongs to a different migration scope")
    else:
        receipt = {
            "schema_version": 1,
            "identity": identity,
            "tables": {},
            "originals": {},
            "publication_allowed": False,
        }
        receipt_write(path, receipt)
    prefix = "recovery/" + run_id + "/" + report["manifest_sha256"]
    manifest = json.loads((directory / "manifest.json").read_bytes())
    for filename in ["manifest.json", *(entry["file"] for entry in manifest["tables"].values())]:
        local = directory / filename
        existing = receipt["tables"].get(filename)
        if existing:
            digest, size = digest_file(local)
            if (digest, size) != (existing["sha256"], existing["size_bytes"]):
                raise ValueError("local backup changed after staging")
            blob = destination.blob(
                prefix + "/tables/" + filename, generation=int(existing["generation"])
            )
            verify_blob(blob, local, digest, size)
            continue
        receipt["tables"][filename] = put_immutable(
            destination, prefix + "/tables/" + filename, local
        )
        receipt_write(path, receipt)
    uris: dict[str, dict[str, dict[str, str]]] = {}
    for script in rows(directory / "script_versions.jsonl"):
        reference = {"project_id": script["project_id"], "script_id": script["script_id"]}
        uris.setdefault(script.get("gcs_uri", ""), {})[canonical(reference).decode()] = reference
    local_objects = directory / "originals"
    local_objects.mkdir(exist_ok=True, mode=0o700)
    for uri, references in uris.items():
        scripts = list(references.values())
        allowed_prefix = "gs://" + intake_bucket + "/"
        if (
            not uri.startswith(allowed_prefix)
            or not uri[len(allowed_prefix) :]
            or len(uri[len(allowed_prefix) :].encode()) > 1024
        ):
            receipt["originals"][uri] = {
                "state": "blocked",
                "code": "source_bucket_or_object_invalid",
                "script_refs": scripts,
            }
            receipt_write(path, receipt)
            continue
        original = receipt["originals"].get(uri)
        object_name = uri[len(allowed_prefix) :]
        if original and original.get("state") == "verified":
            local = local_objects / original["local_file"]
            if digest_file(local) != (original["sha256"], original["size_bytes"]):
                raise ValueError("original backup bytes changed")
            destination_blob = destination.blob(
                original["backup_object"], generation=int(original["backup_generation"])
            )
            verify_blob(destination_blob, local, original["sha256"], original["size_bytes"])
            continue
        if original and original.get("state") == "blocked":
            continue
        try:
            if not original:
                blob = source.blob(object_name)
                observe_source(blob)
                original = {
                    "state": "observed",
                    "generation": str(blob.generation),
                    "size_bytes": int(blob.size),
                    "script_refs": scripts,
                    "historical_original_ambiguous": len(scripts) > 1,
                }
                receipt["originals"][uri] = original
                receipt_write(path, receipt)
            if not 0 < original["size_bytes"] <= MAX_ORIGINAL_BYTES:
                original.update({"state": "blocked", "code": "original_size_outside_limit"})
                receipt_write(path, receipt)
                continue
            blob = source.blob(object_name, generation=int(original["generation"]))
            local_name = (
                hashlib.sha256(uri.encode()).hexdigest() + "-" + original["generation"] + ".bin"
            )
            local = local_objects / local_name
            with tempfile.NamedTemporaryFile(dir=local_objects, delete=False) as temporary:
                downloaded = Path(temporary.name)
            download_source(blob, downloaded, int(original["generation"]))
            digest, size = digest_file(downloaded)
            if size != original["size_bytes"]:
                raise ValueError("source generation size changed")
            if local.exists() and digest_file(local) != (digest, size):
                raise ValueError(
                    "unacknowledged original bytes do not match their pinned generation"
                )
            os.replace(downloaded, local)
            backup_object = prefix + "/originals/" + local_name
            uploaded = put_immutable(destination, backup_object, local)
            original.update(
                {
                    "state": "verified",
                    "sha256": digest,
                    "local_file": local_name,
                    "backup_object": backup_object,
                    "backup_generation": uploaded["generation"],
                }
            )
            receipt_write(path, receipt)
        except MissingSourceGeneration:
            assert original is not None or uri not in receipt["originals"]
            receipt["originals"][uri] = {
                **(original or {}),
                "state": "blocked",
                "code": "source_generation_missing",
                "script_refs": scripts,
            }
            receipt_write(path, receipt)
    return {
        "run_id": run_id,
        "source_manifest_sha256": report["manifest_sha256"],
        "staged_table_files": len(receipt["tables"]),
        "verified_originals": sum(
            value.get("state") == "verified" for value in receipt["originals"].values()
        ),
        "blocked_originals": sum(
            value.get("state") == "blocked" for value in receipt["originals"].values()
        ),
        "ambiguous_historical_originals": sum(
            bool(value.get("historical_original_ambiguous"))
            for value in receipt["originals"].values()
        ),
        "raw_record_status": report["status"],
        "original_revision_fidelity_verified": False,
        "ownership_verified": False,
        "publication_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--intake-bucket", required=True)
    parser.add_argument("--backup-bucket", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", args.project) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,100}", args.run_id
    ):
        parser.error("invalid project or migration run identifier")
    report = verify(args.directory)
    if not args.apply:
        print(
            json.dumps(
                {
                    "run_id": args.run_id,
                    "source_manifest_sha256": report["manifest_sha256"],
                    "backup_bucket": args.backup_bucket,
                    "intake_bucket": args.intake_bucket,
                    "cloud_calls": False,
                    "publication_allowed": False,
                },
                indent=2,
            )
        )
        return
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    from google.cloud import storage

    credentials, _ = google.auth.default(quota_project_id=args.project)
    with AuthorizedSession(credentials) as session:  # type: ignore[no-untyped-call]
        response = session.get(
            "https://cloudresourcemanager.googleapis.com/v3/projects/" + args.project, timeout=30
        )
        if response.status_code != 200:
            raise ValueError("GCP project identity could not be verified")
        project = response.json()
        if project.get("projectId") != args.project or not re.fullmatch(
            r"projects/[0-9]+", project.get("name", "")
        ):
            raise ValueError("unexpected GCP project identity")
    result = stage(
        storage.Client(project=args.project, credentials=credentials),
        args.directory,
        project_number=project["name"].split("/")[-1],
        intake_bucket=args.intake_bucket,
        backup_bucket=args.backup_bucket,
        run_id=args.run_id,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "legacy object backup remains unverified; preserve receipts and artifacts"
        ) from None
