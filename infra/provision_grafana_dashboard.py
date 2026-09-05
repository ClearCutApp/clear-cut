#!/usr/bin/env python3
"""Publish the ClearCut Grafana Cloud dashboard (infrastructure.md section 10).

The four panels query the metric names the adapters emit:
`clearcut_stage_latency_ms`, `clearcut_gemini_tokens_total`,
`clearcut_findings_total`, `clearcut_tracker_items`. The JSON is the only
definition; this script POSTs it.

Usage:
    .venv/bin/python infra/provision_grafana_dashboard.py [--dry-run]

--dry-run prints the uid, titles, and PromQL it would POST and connects to
nothing, so it needs no credentials. A real run reads GRAFANA_URL and
GRAFANA_TOKEN (a Grafana service account, not the OTLP write pair) and
exits naming any that are missing.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Protocol

DASHBOARD_PATH = Path(__file__).resolve().parent / "grafana_dashboard.json"
REQUIRED = ("GRAFANA_URL", "GRAFANA_TOKEN")


class GrafanaClient(Protocol):
    def put_dashboard(self, dashboard: dict[str, Any]) -> None: ...


def load_dashboard() -> dict[str, Any]:
    payload = json.loads(DASHBOARD_PATH.read_text())
    if not isinstance(payload, dict):
        raise TypeError(f"{DASHBOARD_PATH} must contain a JSON object")
    return payload


def describe(dashboard: dict[str, Any]) -> str:
    lines = [f"uid={dashboard['uid']} title={dashboard['title']}"]
    for panel in dashboard["panels"]:
        exprs = ", ".join(str(target.get("expr", "")) for target in panel.get("targets", []))
        lines.append(f"  {panel['title']}: {exprs}")
    return "\n".join(lines)


def publish(client: GrafanaClient, dashboard: dict[str, Any]) -> None:
    """POST the dashboard through the client the caller supplies.

    The HTTP client is the seam that lets a test assert what would be
    published without a Grafana Cloud stack.
    """
    client.put_dashboard(dashboard)


class GrafanaHttp:
    """Grafana HTTP API, POST /api/dashboards/db with overwrite."""

    def __init__(self, base_url: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token

    def put_dashboard(self, dashboard: dict[str, Any]) -> None:
        import httpx

        response = httpx.post(
            f"{self._base_url}/api/dashboards/db",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={"dashboard": dashboard, "overwrite": True},
            timeout=30.0,
        )
        response.raise_for_status()


def _missing_credentials() -> list[str]:
    return [name for name in REQUIRED if not os.environ.get(name, "").strip()]


def _publish_live(dashboard: dict[str, Any]) -> int:
    missing = _missing_credentials()
    if missing:
        print(
            f"provision_grafana_dashboard.py: missing required environment {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1
    import httpx

    try:
        publish(GrafanaHttp(os.environ["GRAFANA_URL"], os.environ["GRAFANA_TOKEN"]), dashboard)
    except httpx.HTTPError as exc:
        print(f"provision_grafana_dashboard.py: Grafana API request failed: {exc}", file=sys.stderr)
        return 1
    print("published:")
    print(describe(dashboard))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    unknown = [arg for arg in args if arg != "--dry-run"]
    if unknown:
        print(f"unexpected argument: {unknown[0]}", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        return 2
    dashboard = load_dashboard()
    if "--dry-run" in args:
        print("would POST /api/dashboards/db:")
        print(describe(dashboard))
        return 0
    return _publish_live(dashboard)


if __name__ == "__main__":
    raise SystemExit(main())
