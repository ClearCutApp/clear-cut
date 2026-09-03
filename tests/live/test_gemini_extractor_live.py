"""`GeminiSceneExtractor` against Vertex AI.

The assertion that carries this test is `clearcut_gemini_tokens_total`. The
adapter records it from `response.usage_metadata` (extractor.py:170-173), and
the hand-written fake in `tests/unit/adapters/test_extractor.py` leaves
`usage_metadata` as `None`. So a recorded token count cannot come through this
seam without a real model call -- it is the one value in the whole pipeline a
fake provably cannot produce.
"""

import pytest
from google import genai

from clearcut.adapters.gemini.extractor import GeminiSceneExtractor
from clearcut.domain.finding import NerLabel
from clearcut.domain.jurisdiction import jurisdiction_for
from clearcut.domain.script import Scene
from tests.live.conftest import env, requires
from tests.unit.conftest import install_in_memory_telemetry, metric_attributes_by_name

_SCENE = Scene(
    number=1,
    heading="INT. BAR - DAY",
    page_start=1,
    page_end=1,
    text=(
        "INT. BAR - DAY\n"
        "A neon Quilmes sign glows over the counter. MARA slides a bottle of\n"
        'Coca-Cola across the bar while "Hotel California" plays on the radio.'
    ),
)


@pytest.mark.live
@requires("GOOGLE_CLOUD_PROJECT", "GEMINI_MODEL")
def test_extracts_findings_from_a_real_scene_and_reports_token_usage(isolated_otel: None) -> None:
    _, metric_reader = install_in_memory_telemetry()
    extractor = GeminiSceneExtractor(
        client=genai.Client(
            vertexai=True,
            project=env("GOOGLE_CLOUD_PROJECT"),
            location="global",  # Gemini 3 is global-only; see composition._GENAI_LOCATION
        ),
        model=env("GEMINI_MODEL"),
    )

    findings = extractor.extract([_SCENE], jurisdiction_for("AR"))

    assert findings, "a scene naming two brands and a song should yield findings"
    for finding in findings:
        assert finding.ner_label is None or finding.ner_label in NerLabel
        assert finding.raw_text.strip()
        assert finding.scene_number == 1

    token_points = metric_attributes_by_name(metric_reader).get("clearcut_gemini_tokens_total", [])
    assert token_points, (
        "no token metric recorded: the adapter only writes this from "
        "response.usage_metadata, which a fake leaves as None"
    )
    assert {point.get("token_type") for point in token_points} >= {"prompt"}
