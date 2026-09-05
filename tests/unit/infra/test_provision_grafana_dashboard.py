"""Behaviour tests for infra/provision_grafana_dashboard.py.

The four panels docs/plan/infrastructure.md section 10 names have to live
in a dashboard JSON this repo can POST to Grafana Cloud. An in-memory
exporter already proves the adapters emit the metrics; this file proves the
dashboard queries those same four names, and that the provision script
prints them under --dry-run without opening a socket.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "infra" / "provision_grafana_dashboard.py"
DASHBOARD = REPO / "infra" / "grafana_dashboard.json"

REQUIRED = ("GRAFANA_URL", "GRAFANA_TOKEN")

PANEL_TITLES = (
    "Stage latency",
    "Tokens per model",
    "Findings by severity",
    "Tracker items by state",
)

METRIC_NAMES = (
    "clearcut_stage_latency_ms",
    "clearcut_gemini_tokens_total",
    "clearcut_findings_total",
    "clearcut_tracker_items",
)


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("provision_grafana_dashboard", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_dashboard_json_has_the_four_section_10_panels() -> None:
    dashboard = json.loads(DASHBOARD.read_text())
    panels = dashboard["panels"]
    titles = [panel["title"] for panel in panels]
    assert titles == list(PANEL_TITLES)

    exprs = " ".join(
        str(target.get("expr", "")) for panel in panels for target in panel.get("targets", [])
    )
    for name in METRIC_NAMES:
        assert name in exprs, f"{name} is missing from panel queries"


def test_dry_run_prints_the_panels_without_connecting() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    for title in PANEL_TITLES:
        assert title in result.stdout
    for name in METRIC_NAMES:
        assert name in result.stdout


@pytest.mark.parametrize("missing", REQUIRED)
def test_a_missing_credential_exits_naming_that_variable(missing: str) -> None:
    env = {name: "placeholder" for name in REQUIRED}
    del env[missing]
    env["PATH"] = "/usr/bin:/bin"

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode != 0
    assert missing in result.stderr, result.stderr


class RecordingGrafana:
    """Records the dashboard the script would POST. The seam `publish`
    takes, so this test never talks to Grafana Cloud."""

    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []

    def put_dashboard(self, dashboard: dict[str, Any]) -> None:
        self.published.append(dashboard)


def test_publish_posts_the_four_panel_dashboard() -> None:
    client = RecordingGrafana()
    dashboard = json.loads(DASHBOARD.read_text())

    load_script().publish(client, dashboard)

    assert len(client.published) == 1
    titles = [panel["title"] for panel in client.published[0]["panels"]]
    assert titles == list(PANEL_TITLES)
