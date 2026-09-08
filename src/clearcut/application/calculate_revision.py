"""Analyze the saved revision bytes and preserve their exact screenplay anchors."""

import json
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from clearcut.application.analysis_documents import finding_data, script_data, tracker_data
from clearcut.application.analysis_steps import AnalysisSteps
from clearcut.application.analyze_script import AnalyzeScript
from clearcut.application.draft_ports import ScreenplayContent
from clearcut.application.revision_scenes import revision_scenes
from clearcut.domain.durable_analysis import DurableJob
from clearcut.domain.jurisdiction import jurisdiction_for
from clearcut.domain.screenplay import ContentReference, encode_document


class CalculateRevision:
    def __init__(
        self,
        content: ScreenplayContent,
        render: Callable[[dict[str, Any], str, str], tuple[bytes, dict[str, tuple[int, int]]]],
        analyzer: Callable[[AnalysisSteps], AnalyzeScript],
    ) -> None:
        self.content, self.render, self.analyzer = content, render, analyzer

    def __call__(self, job: DurableJob, steps: AnalysisSteps) -> dict[str, Any]:
        request = job.request
        document = json.loads(self.content.get(request.revision_content))
        encode_document(document)
        steps.ensure("screenplay_layout")
        saved = steps.read("revision-layout")
        if saved is None:
            pdf, pages = self.render(document, "Screenplay", request.revision_id)
            reference = steps.artifacts.put_bytes(
                request.organization_id,
                request.project_id,
                request.analysis_id,
                "screenplay",
                pdf,
                "application/pdf",
            )
            saved = {"pdf": asdict(reference), "pages": pages}
            steps.write("revision-layout", saved)
        reference = ContentReference(**saved["pdf"])
        pages = {block: (int(value[0]), int(value[1])) for block, value in saved["pages"].items()}
        scenes, anchors = revision_scenes(document, pages)
        report = self.analyzer(steps).calculate(
            request.project_id,
            request.script_id,
            request.script_version,
            reference.uri,
            jurisdiction_for(request.jurisdiction_code),
            request.created_at.isoformat(),
            scenes,
        )
        return {
            "schema_version": 1,
            "analysis_id": request.analysis_id,
            "organization_id": request.organization_id,
            "project_id": request.project_id,
            "revision_id": request.revision_id,
            "revision_draft_version": request.revision_version,
            "revision_content": asdict(request.revision_content),
            "script": script_data(report.script),
            "findings": [finding_data(value) for value in report.findings],
            "tracker_items": [tracker_data(value) for value in report.tracker_items],
            "scene_anchors": anchors,
            "screenplay_pdf": asdict(reference),
            "coverage_gaps": list(steps.gaps.values()),
            "created_at": request.created_at.isoformat(),
        }
