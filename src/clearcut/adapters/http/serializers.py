"""Domain and use-case types, as the JSON `docs/api/openapi.yaml` describes.

One function per schema in that document, and the schema declarations in
`schemas.py` are written against these functions. A serializer lives here
rather than beside its route when two domains need it: a `Finding` is served
by Scripts and described by Tracker, and a `Citation` hangs off both a
finding and an answer.

Every function here reads; none decides. A `Scene`'s hash is the domain's own
`content_hash`, never recomputed, and its spans arrive already resolved from
`domain/highlight.py` -- an adapter that recomputed either would be a second
opinion about what the value is.
"""

from datetime import datetime
from typing import Any

from clearcut.application.answer_project_question import ProjectAnswer
from clearcut.application.get_script import ScriptDetail
from clearcut.application.list_scripts import ScriptListing
from clearcut.application.upload_script_file import StoredScriptFile
from clearcut.domain.analysis import AnalysisJob
from clearcut.domain.bible import BibleFact, ProjectBible
from clearcut.domain.finding import Citation, Finding
from clearcut.domain.highlight import Span
from clearcut.domain.jurisdiction import Jurisdiction
from clearcut.domain.project import Project
from clearcut.domain.script import Scene
from clearcut.domain.tracker import TrackerItem

JsonDict = dict[str, Any]

# `Project.created_at` and `TrackerItem.updated_at` already cross as strings
# in this shape. `AnalysisJob` carries `datetime` instead, because its reaper
# compares times and a string cannot be compared without reparsing it in the
# layer that is meant to hold no format (ADR 0013). This module is where that
# format is applied, on the way out.
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# The one content type this service accepts a screenplay as: Document AI's
# processor is configured for PDF, and `ScriptFile.content_type` in the
# contract is an enum with a single member.
_PDF = "application/pdf"


def timestamp_json(moment: datetime) -> str:
    return moment.strftime(_TIMESTAMP_FORMAT)


def jurisdiction_json(jurisdiction: Jurisdiction) -> JsonDict:
    """The code and its display name. `corpus_prefix` is deliberately absent:
    it names a bucket layout, which is the server's business."""
    return {"code": jurisdiction.code, "display_name": jurisdiction.display_name}


def project_json(project: Project) -> JsonDict:
    return {
        "project_id": project.project_id,
        "title": project.title,
        "jurisdiction_code": project.jurisdiction_code,
        "created_at": project.created_at,
    }


def citation_json(citation: Citation) -> JsonDict:
    return {"uri": citation.uri, "title": citation.title, "snippet": citation.snippet}


def span_json(span: Span) -> JsonDict:
    return {
        "scene_number": span.scene_number,
        "start": span.start,
        "end": span.end,
        "finding_id": span.finding_id,
        "risk": span.risk.value,
    }


def scene_json(scene: Scene, spans: tuple[Span, ...] = ()) -> JsonDict:
    return {
        "number": scene.number,
        "heading": scene.heading,
        "page_start": scene.page_start,
        "page_end": scene.page_end,
        "text": scene.text,
        "content_hash": scene.content_hash,
        "spans": [span_json(span) for span in spans],
    }


def finding_json(finding: Finding) -> JsonDict:
    return {
        "finding_id": finding.finding_id,
        "scene_number": finding.scene_number,
        "page": finding.page,
        "raw_text": finding.raw_text,
        "category": finding.category.value,
        "ner_label": finding.ner_label.value if finding.ner_label is not None else None,
        "risk_level": finding.risk_level.value,
        "required_document": finding.required_document,
        "citations": [citation_json(citation) for citation in finding.citations],
        "contradicts": finding.contradicts,
    }


def tracker_item_json(item: TrackerItem) -> JsonDict:
    return {
        "item_id": item.item_id,
        "project_id": item.project_id,
        "finding_id": item.finding_id,
        "scene_numbers": list(item.scene_numbers),
        "state": item.state.value,
        "needs_review": item.needs_review,
        "required_document": item.required_document,
        "contact": item.contact,
        "litigation_posture": item.litigation_posture,
        "draft_email": item.draft_email,
        "clearance_conditions": item.clearance_conditions,
        "due_date": item.due_date,
        "assignee_id": item.assignee_id,
        "evidence_file_ids": list(item.evidence_file_ids),
        "rights_holder_citations": [
            citation_json(citation) for citation in item.rights_holder_citations
        ],
        "note": item.note,
        "updated_at": item.updated_at,
        "version": item.version,
    }


def bible_fact_json(fact: BibleFact) -> JsonDict:
    return {
        "fact_id": fact.fact_id,
        "kind": fact.kind.value,
        "text": fact.text,
        "source": fact.source,
    }


def project_bible_json(bible: ProjectBible) -> JsonDict:
    return {
        "project_id": bible.project_id,
        "facts": [bible_fact_json(fact) for fact in bible.facts],
    }


def project_answer_json(answer: ProjectAnswer) -> JsonDict:
    return {
        "text": answer.text,
        "facts": [bible_fact_json(fact) for fact in answer.facts],
        "citations": [citation_json(citation) for citation in answer.citations],
    }


def analysis_job_json(job: AnalysisJob) -> JsonDict:
    return {
        "analysis_id": job.analysis_id,
        "project_id": job.project_id,
        "script_id": job.script_id,
        "state": job.state.value,
        "created_at": timestamp_json(job.created_at),
        "updated_at": timestamp_json(job.updated_at),
        "error": job.error,
        "version": job.version,
    }


def script_file_json(stored: StoredScriptFile) -> JsonDict:
    return {
        "gcs_uri": stored.gcs_uri,
        "filename": stored.filename,
        "size_bytes": stored.size_bytes,
        "content_type": _PDF,
    }


def script_summary_json(listing: ScriptListing) -> JsonDict:
    """One version without its scenes or findings, for the list read.

    `scene_count` and `finding_count` are what the list is for: a producer
    picking a version needs to know which one carries the work, and shipping
    every scene of every version to answer that would be the whole script
    several times over.
    """
    script = listing.script
    return {
        "script_id": script.script_id,
        "project_id": script.project_id,
        "version": script.version,
        "gcs_uri": script.gcs_uri,
        "jurisdiction_code": script.jurisdiction_code,
        "scene_count": len(script.scenes),
        "finding_count": listing.finding_count,
    }


def _spans_by_scene(spans: tuple[Span, ...]) -> dict[int, tuple[Span, ...]]:
    grouped: dict[int, list[Span]] = {}
    for span in spans:
        grouped.setdefault(span.scene_number, []).append(span)
    return {number: tuple(found) for number, found in grouped.items()}


def script_json(detail: ScriptDetail) -> JsonDict:
    """One script version with every scene, its spans, and every finding.

    The spans arrive as one flat sequence carrying their own scene numbers,
    and are regrouped here rather than in the use case: a span survives being
    moved because it names its scene, and grouping is a shape the wire wants,
    not a rule about scripts.
    """
    script = detail.script
    grouped = _spans_by_scene(detail.spans)
    return {
        "script_id": script.script_id,
        "project_id": script.project_id,
        "version": script.version,
        "gcs_uri": script.gcs_uri,
        "jurisdiction_code": script.jurisdiction_code,
        "scenes": [scene_json(scene, grouped.get(scene.number, ())) for scene in script.scenes],
        "findings": [finding_json(finding) for finding in detail.findings],
    }
