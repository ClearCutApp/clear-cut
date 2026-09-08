from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from google.api_core.exceptions import NotFound, PreconditionFailed
from infra.backup_legacy_objects import stage
from infra.backup_legacy_state import backup

from tests.unit.infra.test_legacy_backup import Client, fixture


class Blob:
    def __init__(self, bucket: Any, name: str, generation: int | None = None) -> None:
        self.bucket, self.name, self.generation = bucket, name, generation
        self.metadata: dict[str, Any] = {}
        self.size = 0

    def reload(self, **kwargs: Any) -> None:
        versions = self.bucket.objects.get(self.name, {})
        if not versions or (self.generation is not None and self.generation not in versions):
            raise NotFound("missing")  # type: ignore[no-untyped-call]
        self.generation = self.generation or max(versions)
        self.size = len(versions[self.generation])

    def upload_from_filename(self, path: str, **kwargs: Any) -> None:
        assert kwargs["if_generation_match"] == 0 and kwargs["retry"] is None
        if self.name in self.bucket.objects:
            raise PreconditionFailed("exists")  # type: ignore[no-untyped-call]
        self.bucket.objects[self.name] = {1: Path(path).read_bytes()}
        self.generation = 1
        self.bucket.uploads += 1
        if self.bucket.lose_ack:
            self.bucket.lose_ack = False
            raise RuntimeError("accepted response lost")

    def download_to_filename(self, path: str, **kwargs: Any) -> None:
        assert kwargs["retry"] is None
        if self.bucket.fail_download:
            self.bucket.fail_download = False
            raise RuntimeError("interrupted source download")
        self.reload()
        assert kwargs["if_generation_match"] == self.generation
        self.bucket.downloaded_generations.append(self.generation)
        Path(path).write_bytes(self.bucket.objects[self.name][self.generation])


class Bucket:
    def __init__(self, name: str) -> None:
        self.name = name
        self.project_number = "123"
        self.iam_configuration = SimpleNamespace(public_access_prevention="enforced")
        self.objects: dict[str, dict[int, bytes]] = {}
        self.uploads = 0
        self.lose_ack = False
        self.fail_download = False
        self.downloaded_generations: list[int] = []

    def reload(self, **kwargs: Any) -> None:
        assert kwargs["retry"] is None

    def blob(self, name: str, generation: int | None = None) -> Blob:
        return Blob(self, name, generation)


class Storage:
    def __init__(self) -> None:
        self.buckets = {name: Bucket(name) for name in ("intake", "backup")}
        self.buckets["intake"].objects["original.pdf"] = {1: b"original generation one"}

    def bucket(self, name: str) -> Bucket:
        assert name in self.buckets, "never follow a legacy URI into another bucket"
        return self.buckets[name]


def run(storage: Storage, directory: Path) -> dict[str, Any]:
    return stage(
        storage,
        directory,
        project_number="123",
        intake_bucket="intake",
        backup_bucket="backup",
        run_id="run",
    )


def test_immutable_backup_preserves_pinned_bytes_and_idempotently_verifies_every_object(tmp_path):
    data = fixture()
    data["script_versions"].append(deepcopy(data["script_versions"][0]))
    backup(Client(data), tmp_path, ["project"], "source")
    storage = Storage()
    result = run(storage, tmp_path)
    assert result["staged_table_files"] == 6 and result["verified_originals"] == 1
    assert result["ambiguous_historical_originals"] == 0
    assert (
        result["publication_allowed"] is False
        and result["original_revision_fidelity_verified"] is False
    )
    writes = storage.buckets["backup"].uploads
    assert run(storage, tmp_path) == result and storage.buckets["backup"].uploads == writes
    assert any(
        value[1] == b"original generation one"
        for value in storage.buckets["backup"].objects.values()
    )


def test_lost_upload_ack_reuses_same_create_only_object_and_compares_actual_bytes(tmp_path):
    backup(Client(fixture()), tmp_path, ["project"], "source")
    storage = Storage()
    storage.buckets["backup"].lose_ack = True
    with pytest.raises(RuntimeError):
        run(storage, tmp_path)
    assert storage.buckets["backup"].uploads == 1
    assert run(storage, tmp_path)["verified_originals"] == 1
    assert storage.buckets["backup"].uploads == 7


def test_resume_never_substitutes_a_new_source_generation(tmp_path):
    backup(Client(fixture()), tmp_path, ["project"], "source")
    storage = Storage()
    storage.buckets["intake"].fail_download = True
    with pytest.raises(RuntimeError):
        run(storage, tmp_path)
    storage.buckets["intake"].objects["original.pdf"][2] = b"new overwritten original"
    assert run(storage, tmp_path)["verified_originals"] == 1
    assert storage.buckets["intake"].downloaded_generations == [1]
    assert any(
        value[1] == b"original generation one"
        for value in storage.buckets["backup"].objects.values()
    )


def test_deleted_pinned_generation_is_a_gap_not_a_new_original(tmp_path):
    backup(Client(fixture()), tmp_path, ["project"], "source")
    storage = Storage()
    storage.buckets["intake"].fail_download = True
    with pytest.raises(RuntimeError):
        run(storage, tmp_path)
    storage.buckets["intake"].objects["original.pdf"] = {2: b"new original"}
    result = run(storage, tmp_path)
    assert result["blocked_originals"] == 1 and result["verified_originals"] == 0
    assert not storage.buckets["intake"].downloaded_generations


@pytest.mark.parametrize("failure", ["public-backup", "foreign-project", "foreign-source-uri"])
def test_bucket_scope_and_private_backup_preconditions_prevent_unsafe_copies(tmp_path, failure):
    data = fixture()
    if failure == "foreign-source-uri":
        data["script_versions"][0]["gcs_uri"] = "gs://other/secret.pdf"
    backup(Client(data), tmp_path, ["project"], "source")
    storage = Storage()
    if failure == "public-backup":
        storage.buckets["backup"].iam_configuration.public_access_prevention = "inherited"
    if failure == "foreign-project":
        storage.buckets["backup"].project_number = "999"
    if failure == "foreign-source-uri":
        result = run(storage, tmp_path)
        assert result["blocked_originals"] == 1 and result["verified_originals"] == 0
    else:
        with pytest.raises(ValueError):
            run(storage, tmp_path)
        assert storage.buckets["backup"].uploads == 0


def test_existing_backup_content_conflict_is_never_overwritten(tmp_path):
    backup(Client(fixture()), tmp_path, ["project"], "source")
    storage = Storage()
    run(storage, tmp_path)
    first = next(iter(storage.buckets["backup"].objects))
    storage.buckets["backup"].objects[first][1] = b"changed"
    count = storage.buckets["backup"].uploads
    with pytest.raises(ValueError):
        run(storage, tmp_path)
    assert storage.buckets["backup"].uploads == count
