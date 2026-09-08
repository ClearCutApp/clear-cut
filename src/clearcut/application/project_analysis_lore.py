"""Checkpoint vectors before BigQuery and expose only completed revision projections."""

from collections.abc import Callable
from datetime import datetime

from clearcut.application.durable_ports import AnalysisArtifacts
from clearcut.application.lore_projection_ports import LoreLease, LoreProjectionQueue, SceneVectors
from clearcut.domain.durable_analysis import LeaseLost
from clearcut.domain.errors import SourceUnavailable


class ProjectAnalysisLore:
    def __init__(
        self,
        queue: LoreProjectionQueue,
        artifacts: AnalysisArtifacts,
        vectors: SceneVectors,
        clock: Callable[[], datetime],
    ) -> None:
        self.queue, self.artifacts, self.vectors, self.clock = queue, artifacts, vectors, clock

    def execute_batch(self, lease: LoreLease, guard: Callable[[], None]) -> None:
        try:
            guard()
            self.queue.heartbeat(lease, self.clock())
            manifest = self.artifacts.get(lease.manifest)
            if (
                manifest.get("revision_id") != lease.revision_id
                or manifest.get("project_id") != lease.project_id
                or manifest.get("organization_id") != lease.organization_id
            ):
                raise ValueError("projection revision differs from committed manifest")
            anchors = {
                anchor["scene_number"]: anchor["scene_id"] for anchor in manifest["scene_anchors"]
            }
            # Every character is indexed. Byte-bounded excerpts avoid silently
            # truncating a long scene at an embedding model's token boundary.
            scenes = []
            for scene in manifest["script"]["scenes"]:
                start, size = 0, 0
                parts: list[str] = []
                for index, character in enumerate(scene["text"]):
                    width = len(character.encode("utf-8"))
                    if parts and size + width > 1900:
                        scenes.append(
                            {
                                **scene,
                                "text": "".join(parts),
                                "chunk_start": start,
                                "scene_id": anchors[scene["number"]],
                            }
                        )
                        start, size, parts = index, 0, []
                    parts.append(character)
                    size += width
                if parts:
                    scenes.append(
                        {
                            **scene,
                            "text": "".join(parts),
                            "chunk_start": start,
                            "scene_id": anchors[scene["number"]],
                        }
                    )
            end = min(len(scenes), lease.cursor + 8)
            batch = scenes[lease.cursor : end]
            if batch:
                if lease.checkpoint:
                    checkpoint = self.artifacts.get(lease.checkpoint)
                    if (
                        checkpoint["cursor"] != lease.cursor
                        or checkpoint["analysis_id"] != lease.analysis_id
                    ):
                        raise ValueError("projection checkpoint scope mismatch")
                    embeddings = checkpoint["embeddings"]
                else:
                    guard()
                    self.queue.heartbeat(lease, self.clock())
                    embeddings = self.vectors.embed(
                        [s["text"] for s in batch], lease.provider_config_json
                    )
                    checkpoint_ref = self.artifacts.put(
                        lease.organization_id,
                        lease.project_id,
                        lease.analysis_id,
                        f"lore-vectors-{lease.cursor}",
                        {
                            "cursor": lease.cursor,
                            "analysis_id": lease.analysis_id,
                            "embeddings": embeddings,
                        },
                    )
                    guard()
                    self.queue.checkpoint(lease, checkpoint_ref, self.clock())
                guard()
                self.queue.heartbeat(lease, self.clock())
                self.vectors.append(lease, batch, embeddings)
            guard()
            self.queue.advance(lease, end, end == len(scenes), self.clock())
        except LeaseLost:
            return
        except (SourceUnavailable, ValueError, KeyError):
            try:
                self.queue.fail(lease, self.clock())
            except LeaseLost:
                return
