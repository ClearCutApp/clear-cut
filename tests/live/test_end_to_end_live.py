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
from clearcut.composition import create_app
from clearcut.domain.finding import Category, NerLabel
from clearcut.domain.script import content_hash
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

    # Through the HTTP route, not the use case directly. SDD section 6 says
    # "one trace per /api/analyze request", and the root span that ties the
    # five stages together is opened by the route (`routes.py`), not by
    # `AnalyzeScript`. Driving the graph directly produced fifteen orphan
    # traces rather than one -- the spans were all there, with no parent to
    # belong to. It is also the more faithful test: this is the path the demo
    # takes.
    client = create_app().test_client()
    response = client.post(
        f"/api/projects/{scenario.PROJECT_ID}/scripts",
        json={
            "gcs_uri": env("CLEARCUT_LIVE_SCRIPT_GCS_URI"),
            "version": 1,
            "jurisdiction_code": "AR",
        },
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json()

    # --- the three planted findings, section 8(d) ---
    by_category = {Category(f["category"]): f for f in body["findings"]}
    assert Category.INDUSTRIAL_PROPERTY in by_category, "the Ferrari Testarossa did not surface"
    assert Category.COPYRIGHT_WORKS in by_category, '"Hotel California" did not surface'
    assert Category.CONTINUITY in by_category, "the bible contradiction did not surface"

    ferrari = by_category[Category.INDUSTRIAL_PROPERTY]
    song = by_category[Category.COPYRIGHT_WORKS]
    contradiction = by_category[Category.CONTINUITY]

    assert ferrari["ner_label"] == NerLabel.BRAND.value
    assert song["ner_label"] == NerLabel.MUSIC_EXISTING.value
    # A bible finding carries no NER tag, and names the fact it contradicts.
    assert contradiction["ner_label"] is None
    # By content hash, not by "FACT-001". The same round trip that
    # `seed_project_bible.seed` guards against: `BigQueryLoreStore` rebuilds a
    # retrieved fact's `fact_id` from the stored `content_hash` column, so the
    # continuity check cites the id it was actually handed. This assertion said
    # `FACT-001` and failed against the real store, which is the product being
    # right and the test being wrong.
    assert contradiction["contradicts"] == content_hash(scenario.BIBLE_FACT.text)

    # --- the page numbers, which is the half a mocked run cannot prove ---
    # `build_planted_script.py` put the scenes on the pages `scenario.py`
    # declares, and Document AI has to read them back off the real PDF.
    pages = {scene.number: scene.page_start for scene in scenario.SCENES}
    assert ferrari["page"] == pages[1] == 3
    assert song["page"] == pages[2] == 5
    assert contradiction["page"] == pages[3] == 8

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
    listed = client.get(f"/api/projects/{scenario.PROJECT_ID}/tracker-items")
    assert listed.status_code == 200
    stored = {item["finding_id"]: item for item in listed.get_json()}
    for finding in (ferrari, song, contradiction):
        assert finding["finding_id"] in stored, f"{finding['category']} never reached the tracker"
        assert stored[finding["finding_id"]]["state"] == TrackerState.BLOCKED.value

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
