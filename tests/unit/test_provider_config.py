import json

import pytest

from clearcut.provider_config import ProviderConfig


def test_saved_provider_configuration_overrides_later_environment_without_drift():
    original = ProviderConfig.read(
        {
            "CLEARCUT_PROVIDER_OPTIONS": json.dumps(
                {
                    "grounding_model": "grounding-model-v1",
                    "search_timeout": 18.5,
                    "research_result_timeout": 210,
                }
            )
        },
        "extract-v1",
        "continuity-v1",
    )
    resumed = ProviderConfig.read(
        {"CLEARCUT_PROVIDER_OPTIONS": '{"search_timeout":2}'},
        "extract-v2",
        "continuity-v2",
        original.frozen(),
    )
    assert resumed == original
    assert resumed.frozen() == original.frozen()


@pytest.mark.parametrize(
    "options",
    [
        '{"genai_timeout":0}',
        '{"search_timeout":true}',
        '{"search_timeout":"nan"}',
        '{"document_timeout":3601}',
        '{"api_key":"private"}',
        "[]",
        "invalid",
        '{"grounding_model":""}',
        '{"speech_timeout":0.0001}',
    ],
)
def test_invalid_or_secret_provider_options_are_not_persisted(options):
    with pytest.raises(ValueError) as error:
        ProviderConfig.read({"CLEARCUT_PROVIDER_OPTIONS": options}, "extract", "continuity")
    assert "private" not in str(error.value)
