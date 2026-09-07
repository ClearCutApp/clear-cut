"""Validated provider models and budgets, frozen into durable analysis requests."""

import json
import math
import re
from dataclasses import asdict, dataclass, fields
from typing import Mapping


@dataclass(frozen=True)
class ProviderConfig:
    gemini_model: str
    gemini_model_lite: str
    grounding_model: str = "gemini-3.1-flash-lite"
    embedding_model: str = "text-embedding-005"
    speech_model: str = "chirp_2"
    research_processor: str = "core"
    genai_timeout: float = 120
    document_timeout: float = 120
    bigquery_timeout: float = 30
    search_timeout: float = 45
    research_create_timeout: float = 30
    research_result_timeout: float = 300
    speech_timeout: float = 45
    clickhouse_connect_timeout: float = 10
    clickhouse_request_timeout: float = 30

    def __post_init__(self) -> None:
        for definition in fields(self):
            value = getattr(self, definition.name)
            if definition.name.endswith("timeout"):
                if (
                    isinstance(value, bool)
                    or not math.isfinite(value)
                    or not 0.001 <= value <= 3600
                ):
                    raise ValueError(f"invalid provider budget: {definition.name}")
            elif not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._/-]{1,200}", value):
                raise ValueError(f"invalid provider model or processor: {definition.name}")

    def frozen(self) -> dict[str, str]:
        return {
            key: format(value, ".15g") if key.endswith("timeout") else str(value)
            for key, value in asdict(self).items()
        }

    @classmethod
    def read(
        cls,
        env: Mapping[str, str],
        gemini_model: str,
        gemini_model_lite: str,
        saved: Mapping[str, str] | None = None,
    ) -> "ProviderConfig":
        values = asdict(cls(gemini_model, gemini_model_lite))
        if saved is None:
            try:
                overrides = json.loads(env.get("CLEARCUT_PROVIDER_OPTIONS", "{}"))
            except (ValueError, TypeError):
                raise ValueError("CLEARCUT_PROVIDER_OPTIONS must be a JSON object") from None
        else:
            overrides = dict(saved)
        if not isinstance(overrides, dict) or set(overrides) - set(values):
            raise ValueError("provider options contain unsupported fields")
        for key, value in overrides.items():
            if key.endswith("timeout"):
                if isinstance(value, bool):
                    raise ValueError(f"invalid provider budget: {key}")
                try:
                    values[key] = float(value)
                except (TypeError, ValueError):
                    raise ValueError(f"invalid provider budget: {key}") from None
            else:
                values[key] = value
        return cls(**values)
