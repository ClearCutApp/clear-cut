"""The provisioning scripts and the adapters must agree on identifier shape.

This is the test that would have caught both bugs D66 records. `.env` is written
by `infra/*.sh` and read by `composition.py`, which passes each value straight
into an SDK call -- but the two sides were only ever tested apart, each against
a hand-written fake that accepts any string. So the scripts printed one shape,
the adapters required another, and 477 green tests said nothing.

Nothing here needs credentials or a project. It compares what the scripts print
under `--dry-run` against the shape each SDK call demands, which is a fact about
the code rather than about any deployment.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

INFRA = Path(__file__).resolve().parents[3] / "infra"
DATA_PLANE = INFRA / "provision_data_plane.sh"
RETRIEVAL_PLANE = INFRA / "provision_retrieval_plane.sh"

# `DocumentAIIngestion.parse` puts DOCAI_PROCESSOR_ID into
# `ProcessRequest(name=...)` (adapters/gcp/document_ai.py:149), which the API
# rejects unless it is a complete resource name.
DOCAI_NAME = re.compile(r"^projects/[^/]+/locations/[^/]+/processors/[^/]+$")

# `VertexSearchGrounding._grounded_config` puts VERTEX_SEARCH_DATA_STORE_ID into
# `types.VertexAISearch(datastore=...)` (adapters/gcp/vertex_search.py:92), which
# needs the collection segment too.
DATA_STORE_NAME = re.compile(r"^projects/[^/]+/locations/[^/]+/collections/[^/]+/dataStores/[^/]+$")


def _location_of(value: str) -> str:
    """The `locations/<x>` segment of a resource path.

    Asserts rather than indexing blind: when the path is malformed the useful
    failure names the value, not `IndexError: list index out of range`.
    """
    parts = value.split("/locations/")
    assert len(parts) == 2, f"{value!r} has no /locations/ segment"
    return parts[1].split("/")[0]


def _env_value(script: Path, key: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["/bin/bash", str(script), "--dry-run"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    prefix = f"{key}="
    lines = [line for line in result.stdout.splitlines() if line.startswith(prefix)]
    assert len(lines) == 1, f"{script.name} printed {len(lines)} {key} lines, expected 1"
    return lines[0][len(prefix) :]


@pytest.fixture
def manifest_env(tmp_path: Path) -> dict[str, str]:
    manifest = tmp_path / "legal_corpus_manifest.jsonl"
    manifest.write_text(
        '{"id": "argentina-ley-11723", "structData": {"jurisdiction": "argentina"}, '
        '"content": {"mimeType": "application/pdf", '
        '"uri": "gs://clearcut-legal-corpus/argentina/ley-11723.pdf"}}\n'
    )
    return {**os.environ, "MANIFEST_FILE": str(manifest)}


def test_docai_processor_id_is_printed_as_a_full_resource_name() -> None:
    value = _env_value(DATA_PLANE, "DOCAI_PROCESSOR_ID")

    assert DOCAI_NAME.match(value), (
        f"provision_data_plane.sh prints DOCAI_PROCESSOR_ID={value!r}, which "
        "ProcessRequest(name=...) rejects. It needs "
        "projects/P/locations/L/processors/ID."
    )


def test_data_store_id_is_printed_as_a_full_resource_name(manifest_env: dict[str, str]) -> None:
    value = _env_value(RETRIEVAL_PLANE, "VERTEX_SEARCH_DATA_STORE_ID", env=manifest_env)

    assert DATA_STORE_NAME.match(value), (
        f"provision_retrieval_plane.sh prints VERTEX_SEARCH_DATA_STORE_ID={value!r}, "
        "which types.VertexAISearch(datastore=...) rejects. It needs "
        "projects/P/locations/L/collections/C/dataStores/ID."
    )


def test_the_data_store_location_matches_where_the_script_creates_it(
    manifest_env: dict[str, str],
) -> None:
    """The printed path's location segment is the one the store is created at.

    These drifted apart silently: the script created the store at `global` while
    the adapter's unit test asserted `us`. Both passed, because the fake under
    test accepts any string, and the mismatch could only surface as a failed
    lookup against a store that does not exist at that path.
    """
    source = RETRIEVAL_PLANE.read_text()
    declared = re.search(r'^LOCATION="([^"]+)"', source, re.MULTILINE)
    assert declared, "provision_retrieval_plane.sh no longer declares LOCATION"

    value = _env_value(RETRIEVAL_PLANE, "VERTEX_SEARCH_DATA_STORE_ID", env=manifest_env)
    segment = _location_of(value)

    assert segment == declared.group(1), (
        f"the script creates the data store at {declared.group(1)!r} but prints a "
        f"path under {segment!r}"
    )


def test_the_adapter_unit_test_uses_the_shape_the_script_prints(
    manifest_env: dict[str, str],
) -> None:
    """`test_vertex_search.py`'s constant agrees with the provisioning script.

    That fixture is the only place the expected identifier shape is written
    down on the adapter side. When it disagrees with the script, one of the two
    is wrong and neither test can tell which.
    """
    fixture = (
        Path(__file__).resolve().parents[2] / "unit" / "adapters" / "test_vertex_search.py"
    ).read_text()
    value = _env_value(RETRIEVAL_PLANE, "VERTEX_SEARCH_DATA_STORE_ID", env=manifest_env)
    location = _location_of(value)

    assert f"locations/{location}/collections" in fixture, (
        f"the script prints a path under locations/{location}, which "
        "tests/unit/adapters/test_vertex_search.py does not use"
    )
