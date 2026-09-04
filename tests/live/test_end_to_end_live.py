"""SDD section 8(d) against live services. The submission's evidence.

Nine other live tests each prove one adapter against the service it wraps. This
is the first thing that runs all eight together, through the real
`_build_live_use_cases` graph rather than a hand-assembled one, so it proves the
wiring as well as the services.

What it asserts is section 8(d) verbatim: the Ferrari Testarossa, "Hotel
California" and one contradiction of a seeded bible fact all surface with the
correct page numbers, and the tracker reads exactly three open items at
BLOCKED.

**Minutes, not seconds.** Parallel's `core` processor takes 77 to 169 seconds
per rights lookup and enrichment is a sequential loop, so a full run is several
minutes. That is also why the deployed service needed its Cloud Run request
timeout raised from the 300-second default.

The Grafana half of 8(d) is asserted here as spans and metrics recorded in
process. Whether they arrive in Grafana is a separate question this cannot
answer: OTLP failures over HTTP are silent, so a successful export proves
nothing about receipt. Check the dashboard.
"""

from __future__ import annotations

import pytest

from clearcut.adapters.demo import scenario
from clearcut.composition import _build_live_use_cases
from clearcut.domain.finding import Category, NerLabel
from clearcut.domain.jurisdiction import jurisdiction_for
from clearcut.domain.tracker import TrackerState
from tests.live.conftest import env, requires
from tests.unit.conftest import install_in_memory_telemetry, metric_attributes_by_name

_STAGES = {"ingest", "extract", "ground", "research", "track"}

_LIVE_ENV = (
    "GOOGLE_CLOUD_PROJECT",
    "DOCAI_PROCESSOR_ID",
    "GEMINI_MODEL",
    "GEMINI_MODEL_LITE",
    "VERTEX_SEARCH_DATA_STORE_ID",
    "PARALLEL_API_KEY",
    "CLICKHOUSE_HOST",
    "CLICKHOUSE_USER",
    "CLICKHOUSE_PASSWORD",
    "NOTIFY_WEBHOOK_URL",
    "CLEARCUT_LIVE_SCRIPT_GCS_URI",
)


@pytest.mark.live
@requires(*_LIVE_ENV)
def test_the_planted_script_analyzes_end_to_end(isolated_otel: None) -> None:
    span_exporter, metric_reader = install_in_memory_telemetry()
    graph = _build_live_use_cases()

    report = graph.analyze_script.execute(
        scenario.PROJECT_ID,
        "sdd-8d-live",
        1,
        env("CLEARCUT_LIVE_SCRIPT_GCS_URI"),
        jurisdiction_for("AR"),
        "2026-09-03T00:00:00Z",
    )

    # --- the three planted findings, section 8(d) ---
    by_category = {finding.category: finding for finding in report.findings}
    assert Category.INDUSTRIAL_PROPERTY in by_category, "the Ferrari Testarossa did not surface"
    assert Category.COPYRIGHT_WORKS in by_category, '"Hotel California" did not surface'
    assert Category.CONTINUITY in by_category, "the bible contradiction did not surface"

    ferrari = by_category[Category.INDUSTRIAL_PROPERTY]
    song = by_category[Category.COPYRIGHT_WORKS]
    contradiction = by_category[Category.CONTINUITY]

    assert ferrari.ner_label is NerLabel.BRAND
    assert song.ner_label is NerLabel.MUSIC_EXISTING
    # A bible finding carries no NER tag, and names the fact it contradicts.
    assert contradiction.ner_label is None
    assert contradiction.contradicts == scenario.BIBLE_FACT.fact_id

    # --- the page numbers, which is the half a mocked run cannot prove ---
    # `build_planted_script.py` put the scenes on the pages `scenario.py`
    # declares, and Document AI has to read them back off the real PDF.
    pages = {scene.number: scene.page_start for scene in scenario.SCENES}
    assert ferrari.page == pages[1] == 3
    assert song.page == pages[2] == 5
    assert contradiction.page == pages[3] == 8

    # --- the tracker, read back from ClickHouse rather than from the report ---
    #
    # Section 8(d) says "the tracker reads exactly 3 open items". That clause
    # does not survive contact with a real model, and this test says so rather
    # than suppressing it. The first live run found a fourth: a
    # PERSONALITY_IMAGE location release on scene 8, off "LOLA's father walks
    # through the front door" -- a person and a private house, which is exactly
    # what a clearance extractor should notice.
    #
    # So the assertion is that each planted finding reached the tracker at
    # BLOCKED, which is what proves the pipeline. Counting the total would test
    # the model's restraint instead, and a finding the model was right to make
    # would fail a check about wiring.
    stored = {
        item.finding_id: item for item in graph.list_tracker_items.execute(scenario.PROJECT_ID)
    }
    for finding in (ferrari, song, contradiction):
        assert finding.finding_id in stored, f"{finding.category} never reached the tracker"
        assert stored[finding.finding_id].state is TrackerState.BLOCKED

    # --- the trace: five stages, one id, real tokens ---
    names = {span.name for span in span_exporter.get_finished_spans()}
    assert _STAGES <= names, f"missing stage spans: {sorted(_STAGES - names)}"

    trace_ids = {
        span.context.trace_id
        for span in span_exporter.get_finished_spans()
        if span.name in _STAGES and span.context is not None
    }
    assert len(trace_ids) == 1, "the five stages did not share one trace"

    metrics = metric_attributes_by_name(metric_reader)
    assert metrics.get("clearcut_gemini_tokens_total"), (
        "no token metric: the adapter writes this only from a real "
        "response's usage_metadata, so an empty one means nothing reached Gemini"
    )
    assert metrics.get("clearcut_stage_latency_ms")
