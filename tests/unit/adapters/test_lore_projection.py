from dataclasses import asdict
from datetime import timedelta
from typing import Any
from unittest.mock import Mock

import pytest

from clearcut.adapters.gcp.lore_projection import FirestoreLoreProjection
from clearcut.application.current_scene_lore import CurrentSceneLore
from clearcut.application.project_analysis_lore import ProjectAnalysisLore
from clearcut.domain.durable_analysis import LeaseLost
from clearcut.domain.errors import SourceUnavailable
from tests.unit.adapters.test_clearance_transactions import AtomicClient
from tests.unit.adapters.test_durable_jobs import NOW
from tests.unit.application.test_analysis_checkpoints import Artifacts


def fixture(text: str = "INT. HOME - DAY\nA person enters.") -> tuple[Any, ...]:
    client = AtomicClient()
    artifacts = Artifacts()
    manifest = artifacts.put(
        "org",
        "project",
        "analysis",
        "result",
        {
            "revision_id": "revision",
            "project_id": "project",
            "organization_id": "org",
            "script": {
                "scenes": [{"number": 1, "page_start": 1, "text": text, "content_hash": "hash"}]
            },
            "scene_anchors": [{"scene_number": 1, "scene_id": "stable-scene"}],
        },
    )
    client.data = {
        "project_access/project": {"organization_id": "org", "committed_analysis_id": "analysis"},
        "lore_outbox/analysis": {
            "organization_id": "org",
            "project_id": "project",
            "revision_id": "revision",
            "manifest": asdict(manifest),
            "provider_config_json": "{}",
            "state": "pending",
            "cursor": 0,
            "attempt": 0,
            "available_at": NOW,
        },
    }
    queue = FirestoreLoreProjection(client)
    vectors = Mock()
    vectors.embed.side_effect = lambda texts, _: [[1.0] for text in texts]
    return client, queue, artifacts, vectors


def test_checkpointed_vectors_resume_after_unknown_bigquery_append_without_reembedding():
    client, queue, artifacts, vectors = fixture()
    vectors.append.side_effect = [SourceUnavailable("accepted but response lost"), None]
    now = [NOW]
    projector = ProjectAnalysisLore(queue, artifacts, vectors, lambda: now[0])
    lease = queue.claim("analysis", "first", NOW)
    assert lease is not None
    assert queue.claim("analysis", "duplicate", NOW) is None
    projector.execute_batch(lease, lambda: None)
    assert client.data["lore_outbox/analysis"]["checkpoint"]
    now[0] += timedelta(seconds=61)
    recovered = queue.claim("analysis", "second", now[0])
    assert recovered is not None and recovered.checkpoint is not None
    projector.execute_batch(recovered, lambda: None)
    assert vectors.embed.call_count == 1 and vectors.append.call_count == 2
    assert queue.current("project")["state"] == "ready"
    assert queue.claim("analysis", "duplicate", now[0]) is None


def test_all_unicode_scene_characters_are_indexed_in_bounded_excerpts():
    original = "🎬" * 3000 + "España acción. " * 2000
    client, queue, artifacts, vectors = fixture(original)
    indexed = []
    vectors.append.side_effect = lambda lease, scenes, embeddings: indexed.extend(scenes)
    projector = ProjectAnalysisLore(queue, artifacts, vectors, lambda: NOW)
    while client.data["lore_outbox/analysis"]["state"] != "ready":
        lease = queue.claim("analysis", "worker", NOW)
        assert lease is not None
        projector.execute_batch(lease, lambda: None)
    assert "".join(scene["text"] for scene in indexed) == original
    assert all(len(scene["text"].encode()) <= 1900 for scene in indexed)
    assert {scene["scene_id"] for scene in indexed} == {"stable-scene"}
    assert all(len(call.args[0]) <= 8 for call in vectors.embed.call_args_list)


def test_expired_fence_cannot_publish_and_new_analysis_does_not_use_old_scene_index():
    client, queue, artifacts, vectors = fixture()
    stale = queue.claim("analysis", "old", NOW)
    assert stale is not None
    latest = queue.claim("analysis", "new", NOW + timedelta(seconds=91))
    assert latest is not None
    with pytest.raises(LeaseLost):
        queue.advance(stale, 1, True, NOW + timedelta(seconds=92))
    answer = CurrentSceneLore(queue, vectors)
    assert "not indexed yet" in answer.answer("project", "Who is here?").text
    vectors.search.assert_not_called()
    client.data["lore_outbox/analysis"]["state"] = "ready"
    client.data["project_access/project"]["committed_analysis_id"] = "new-analysis"
    assert "not indexed yet" in answer.answer("project", "Who is here?").text
    vectors.search.assert_not_called()


def test_lease_loss_during_embedding_prevents_bigquery_and_checkpoint_publication():
    client, queue, artifacts, vectors = fixture()
    lease = queue.claim("analysis", "worker", NOW)
    assert lease is not None

    def lose(texts, config):
        client.data["lore_outbox/analysis"]["fence"] += 1
        return [[1.0] for text in texts]

    vectors.embed.side_effect = lose
    ProjectAnalysisLore(queue, artifacts, vectors, lambda: NOW).execute_batch(lease, lambda: None)
    vectors.append.assert_not_called()
    assert not client.data["lore_outbox/analysis"].get("checkpoint")


def test_ready_scene_evidence_links_exact_revision_and_rechecks_publication_race():
    client, queue, _, vectors = fixture()
    client.data["lore_outbox/analysis"]["state"] = "ready"
    rows = [
        {
            "revision_id": "revision",
            "scene_id": "stable-scene",
            "scene_number": 1,
            "page": 1,
            "source": "Revision revision, scene 1, excerpt at character 0",
            "text": "Cited scene",
        }
    ]
    vectors.search.return_value = rows
    answer = CurrentSceneLore(queue, vectors)
    cited = answer.answer("project", "Who enters?")
    assert cited.citations[0].uri == "/projects/project/editor?revision=revision&scene=stable-scene"
    assert cited.citations[0].snippet == "Cited scene"

    def publish_new(*args):
        client.data["project_access/project"]["committed_analysis_id"] = "new-analysis"
        return rows

    vectors.search.side_effect = publish_new
    changed = answer.answer("project", "Who enters?")
    assert changed.citations == () and "newer analysis" in changed.text
