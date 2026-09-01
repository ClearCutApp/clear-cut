"""Unit tests for `composition.py`'s app factory and mode switch (CP-048,
D36, D38).

The headline test (`test_mock_mode_...`) clears the environment down to
`CLEARCUT_MODE=mock` and drives `POST /api/analyze` then `GET /api/tracker`
through a real Flask test client -- the whole of D36 in one test, per
CHECKPOINTS.md's own framing: the MVP runs today, on nothing.
"""

import logging
import os

import pytest
from flask import Flask

from clearcut.adapters.demo.in_memory import (
    InMemoryContinuityCheck,
    InMemoryLegalGrounding,
    InMemoryLoreStore,
    InMemoryNotifier,
    InMemoryRightsResearch,
    InMemorySceneExtractor,
    InMemoryScriptIngestion,
    InMemoryTrackerStore,
)
from clearcut.composition import _build_live_use_cases, _build_mock_use_cases, create_app

_ANALYZE_BODY = {
    "project_id": "demo-project",
    "jurisdiction_code": "AR",
    "gcs_uri": "gs://clearcut-demo/planted-script-v1.pdf",
    "version": 1,
}


def _clear_env(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    """Replaces `os.environ` outright, so a test proves mock mode reads
    nothing beyond `CLEARCUT_MODE` rather than merely not reading twelve
    named variables that happen to be unset in this shell."""
    monkeypatch.setattr(os, "environ", dict(overrides))


# ---------------------------------------------------------------------------
# Criterion 1: create_app() mounts CP-029's blueprint through its frozen
# five-argument factory.
# ---------------------------------------------------------------------------


def test_create_app_returns_a_flask_app_with_the_demo_routes_mounted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch, CLEARCUT_MODE="mock")
    app = create_app()
    assert isinstance(app, Flask)
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/analyze" in rules
    assert "/api/tracker" in rules


# ---------------------------------------------------------------------------
# Criterion 2: CLEARCUT_MODE selects the wiring; mock builds the demo
# adapters, by type.
# ---------------------------------------------------------------------------


def test_build_mock_use_cases_wires_the_demo_adapters_by_type() -> None:
    graph = _build_mock_use_cases()
    assert isinstance(graph.analyze_script._ingestion, InMemoryScriptIngestion)
    assert isinstance(graph.analyze_script._extractor, InMemorySceneExtractor)
    assert isinstance(graph.analyze_script._grounding, InMemoryLegalGrounding)
    assert isinstance(graph.analyze_script._research, InMemoryRightsResearch)
    assert isinstance(graph.analyze_script._lore, InMemoryLoreStore)
    assert isinstance(graph.analyze_script._tracker, InMemoryTrackerStore)
    assert isinstance(graph.analyze_script._continuity, InMemoryContinuityCheck)
    assert isinstance(graph.evaluate_delta._notifier, InMemoryNotifier)
    assert isinstance(graph.list_tracker_items._tracker, InMemoryTrackerStore)
    assert isinstance(graph.resolve_finding._notifier, InMemoryNotifier)
    assert isinstance(graph.answer_project_question._lore, InMemoryLoreStore)


def test_build_mock_use_cases_shares_one_tracker_store_across_use_cases() -> None:
    """`POST /api/analyze` writes through `AnalyzeScript`; `GET /api/tracker`
    reads through `ListTrackerItems`. Two separate `InMemoryTrackerStore`
    instances would make the second call blind to the first call's write."""
    graph = _build_mock_use_cases()
    assert graph.analyze_script._tracker is graph.list_tracker_items._tracker
    assert graph.analyze_script._tracker is graph.resolve_finding._tracker


# ---------------------------------------------------------------------------
# Criterion 3: mock mode needs no credentials, opens no socket, and drives
# the SDD Section 8(d) scenario end to end over a fully cleared environment.
# ---------------------------------------------------------------------------


def test_mock_mode_needs_no_credentials_and_drives_the_sdd_8d_scenario(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch, CLEARCUT_MODE="mock")
    client = create_app().test_client()

    analyze_response = client.post("/api/analyze", json=_ANALYZE_BODY)
    assert analyze_response.status_code == 200
    report = analyze_response.get_json()

    findings_by_category = {finding["category"]: finding for finding in report["findings"]}
    assert len(report["findings"]) == 3
    assert findings_by_category["INDUSTRIAL_PROPERTY"]["page"] == 3
    assert findings_by_category["COPYRIGHT_WORKS"]["page"] == 5
    assert findings_by_category["CONTINUITY"]["page"] == 8

    tracker_response = client.get("/api/tracker?project_id=demo-project")
    assert tracker_response.status_code == 200
    items = tracker_response.get_json()
    assert len(items) == 3
    assert all(item["state"] == "BLOCKED" for item in items)


# ---------------------------------------------------------------------------
# Criterion 4: an unrecognized CLEARCUT_MODE fails at startup naming the
# variable and both accepted values.
# ---------------------------------------------------------------------------


def test_unrecognized_mode_fails_at_startup_naming_the_variable_and_both_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch, CLEARCUT_MODE="demo")
    with pytest.raises(ValueError, match="CLEARCUT_MODE"):
        create_app()
    _clear_env(monkeypatch, CLEARCUT_MODE="demo")
    with pytest.raises(ValueError, match="mock"):
        create_app()
    _clear_env(monkeypatch, CLEARCUT_MODE="demo")
    with pytest.raises(ValueError, match="live"):
        create_app()


# ---------------------------------------------------------------------------
# Criterion 5: live mode fails at startup naming the live wiring as
# incomplete, and never falls back to mock.
# ---------------------------------------------------------------------------


def test_live_mode_fails_at_startup_naming_the_live_wiring_as_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch, CLEARCUT_MODE="live")
    with pytest.raises(RuntimeError, match="live"):
        create_app()


def test_live_wiring_itself_raises_rather_than_returning_a_mock_wired_graph() -> None:
    """Proves the failure originates inside the live branch's own wiring
    function, not somewhere in `create_app()` that could be bypassed --
    so the live branch never quietly returns the mock-wired graph."""
    with pytest.raises(RuntimeError):
        _build_live_use_cases()


def test_absent_mode_defaults_to_live_and_fails_the_same_way(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch)
    with pytest.raises(RuntimeError, match="live"):
        create_app()


# ---------------------------------------------------------------------------
# Criterion 6: mock mode announces itself once at startup with a WARNING.
# ---------------------------------------------------------------------------


def test_mock_mode_logs_exactly_one_startup_warning_naming_the_mode(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _clear_env(monkeypatch, CLEARCUT_MODE="mock")
    with caplog.at_level(logging.WARNING):
        create_app()
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "mock" in warnings[0].message


# ---------------------------------------------------------------------------
# Criterion 7: plain constructor injection; two create_app() calls produce
# independent instances.
# ---------------------------------------------------------------------------


def test_two_create_app_calls_produce_independent_instances(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch, CLEARCUT_MODE="mock")
    first_client = create_app().test_client()
    _clear_env(monkeypatch, CLEARCUT_MODE="mock")
    second_client = create_app().test_client()

    first_client.post("/api/analyze", json=_ANALYZE_BODY)
    second_tracker = second_client.get("/api/tracker?project_id=demo-project")

    assert second_tracker.get_json() == []
