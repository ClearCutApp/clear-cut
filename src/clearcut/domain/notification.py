"""Explicit private-project destination identity, independent of delivery transport."""

import hashlib
import json
import re
from typing import Any


def binding_fingerprint(binding: dict[str, Any]) -> str:
    fields = (
        "organization_id",
        "project_ids",
        "version",
        "endpoint_env",
        "endpoint_sha256",
        "enabled",
    )
    return hashlib.sha256(
        json.dumps({key: binding.get(key) for key in fields}, sort_keys=True).encode()
    ).hexdigest()


def valid_binding(binding: dict[str, Any], organization_id: str, project_id: str) -> bool:
    return (
        binding.get("enabled") is True
        and binding.get("organization_id") == organization_id
        and isinstance(binding.get("project_ids"), list)
        and all(isinstance(value, str) for value in binding["project_ids"])
        and project_id in binding["project_ids"]
        and type(binding.get("version")) is int
        and binding["version"] > 0
        and isinstance(binding.get("endpoint_env"), str)
        and isinstance(binding.get("endpoint_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", binding["endpoint_sha256"]) is not None
        and re.fullmatch(r"[A-Z][A-Z0-9_]{1,99}", binding["endpoint_env"]) is not None
    )
