"""Script and Scene, the units of analysis, chunking, and hashing.

docs/plan/sdd.md Section 2.
"""

import hashlib
import re
from dataclasses import dataclass, field

_WHITESPACE_RUN = re.compile(r"\s+")


def content_hash(text: str) -> str:
    """SHA-256 hex digest of `text`, normalized so identical scenes hash equal.

    Normalization: lowercase, whitespace runs collapsed to one space, and
    leading/trailing whitespace stripped. This is the identity delta
    evaluation joins on across script versions (docs/plan/sdd.md Section 2).
    """
    normalized = _WHITESPACE_RUN.sub(" ", text.strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Scene:
    number: int
    heading: str
    page_start: int
    page_end: int
    text: str
    content_hash: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "content_hash", content_hash(self.text))


def _numbers_strictly_increase(scenes: list[Scene]) -> bool:
    numbers = [scene.number for scene in scenes]
    return all(later > earlier for earlier, later in zip(numbers, numbers[1:]))


@dataclass(frozen=True, slots=True)
class Script:
    script_id: str
    project_id: str
    version: int
    gcs_uri: str
    jurisdiction_code: str
    scenes: list[Scene]

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError(f"version must be >= 1, got {self.version}")
        if not _numbers_strictly_increase(self.scenes):
            raise ValueError("scene numbers must be strictly increasing")
