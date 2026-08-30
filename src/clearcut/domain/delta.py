"""Diff two script versions by scene content hash.

docs/plan/sdd.md Section 4.3; ADR 0007. The scene is the delta unit and
`content_hash` is its identity: a scene that reads the same hashes the same
regardless of where it sits in either version's scene list. The join key
across versions is `number` plus `heading`; the comparison is `content_hash`.
"""

import enum
from dataclasses import dataclass

from clearcut.domain.script import Scene

_SceneKey = tuple[int, str]


class DeltaKind(enum.StrEnum):
    """What happened to a scene between two script versions."""

    ADDED = "ADDED"
    CHANGED = "CHANGED"
    REMOVED = "REMOVED"
    UNCHANGED = "UNCHANGED"


@dataclass(frozen=True)
class SceneDelta:
    """One scene's fate between the old and the new script version."""

    scene_number: int
    heading: str
    kind: DeltaKind
    old_hash: str | None
    new_hash: str | None


def _index_by_key(scenes: list[Scene]) -> dict[_SceneKey, Scene]:
    index: dict[_SceneKey, Scene] = {}
    for scene in scenes:
        key = (scene.number, scene.heading)
        if key in index:
            raise ValueError(
                f"duplicate scene key: number={scene.number}, heading={scene.heading!r}"
            )
        index[key] = scene
    return index


def _delta_for(key: _SceneKey, old_scene: Scene | None, new_scene: Scene | None) -> SceneDelta:
    scene_number, heading = key
    old_hash = old_scene.content_hash if old_scene is not None else None
    new_hash = new_scene.content_hash if new_scene is not None else None

    if old_scene is None:
        kind = DeltaKind.ADDED
    elif new_scene is None:
        kind = DeltaKind.REMOVED
    elif old_hash == new_hash:
        kind = DeltaKind.UNCHANGED
    else:
        kind = DeltaKind.CHANGED

    return SceneDelta(scene_number, heading, kind, old_hash, new_hash)


def diff_scenes(old: list[Scene], new: list[Scene]) -> list[SceneDelta]:
    """Compare two script versions scene by scene.

    Scenes join on `(number, heading)`. A joined pair is UNCHANGED when the
    hashes match and CHANGED when they don't. A key present only in `old` is
    REMOVED; a key present only in `new` is ADDED.
    """
    old_index = _index_by_key(old)
    new_index = _index_by_key(new)

    deltas = [
        _delta_for(key, old_scene, new_index.get(key)) for key, old_scene in old_index.items()
    ]
    deltas += [
        _delta_for(key, None, new_scene)
        for key, new_scene in new_index.items()
        if key not in old_index
    ]
    return deltas
