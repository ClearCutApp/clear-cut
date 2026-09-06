"""Reads one script version with its findings and their highlight spans
(docs/api/openapi.yaml, `GET /api/projects/{project_id}/scripts/{script_id}`).

The Script Review screen marks flagged text inline, so the response carries
character offsets rather than the phrases themselves. Computing them on read
is ADR 0015: `Finding` stores `raw_text`, no offsets are ever asked of the
extractor, and the search that turns one into the other is
`domain/highlight.spans_for`. This use case calls it once per scene and joins
the results; every rule about what gets marked -- repeated phrases, overlaps
between two findings, a `raw_text` the scene no longer contains -- belongs to
that function and is not restated or filtered here.

Spans come back as one flat tuple in scene order rather than grouped by
scene. `Span` repeats `scene_number` for exactly that reason, and the route
groups them onto each `Scene` when it serializes.
"""

from dataclasses import dataclass

from clearcut.application.ports import FindingStore, ScriptStore
from clearcut.domain.finding import Finding
from clearcut.domain.highlight import Span, spans_for
from clearcut.domain.script import Script


@dataclass(frozen=True)
class ScriptDetail:
    """One script version, the findings raised against it, and where they land.

    `spans` is shorter than `findings` when a phrase no longer appears in the
    scene it was raised on, and longer when one appears more than once, so
    the two are separate fields rather than one nested structure.
    """

    script: Script
    findings: tuple[Finding, ...]
    spans: tuple[Span, ...]


class GetScript:
    """`GetScript(scripts, findings)`."""

    def __init__(self, scripts: ScriptStore, findings: FindingStore) -> None:
        self._scripts = scripts
        self._findings = findings

    def execute(self, project_id: str, script_id: str) -> ScriptDetail:
        """The version, its findings, and the spans they mark on its scenes.

        `RecordNotFound` from `ScriptStore.get` propagates: the route turns it
        into the contract's 404, and there is no partial answer this use case
        could give for a version that does not exist.

        Every finding is offered to every scene. An asset deduplicated across
        scenes carries one finding for all of them, so filtering by
        `scene_number` first would leave every scene but the first unmarked.
        """
        script = self._scripts.get(project_id, script_id)
        findings = tuple(self._findings.for_script(project_id, script_id))
        spans = tuple(span for scene in script.scenes for span in spans_for(scene, findings))
        return ScriptDetail(script=script, findings=findings, spans=spans)
