"""Private provider exception chains must not enter traces, responses or job rows."""

import ast
from pathlib import Path

import pytest
from flask import Flask
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from clearcut.adapters.http.errors import run_use_case
from clearcut.application.start_analysis import _failure_reason
from clearcut.domain.errors import SourceUnavailable
from clearcut.observability import stage_span

_SENTINEL = "PRIVATE_SCREENPLAY_OR_CREDENTIAL_SENTINEL"


def test_nested_exception_chains_emit_only_safe_stage_failure():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("privacy-test")
    with pytest.raises(SourceUnavailable):
        with stage_span(tracer, "analysis"):
            with stage_span(tracer, "provider"):
                try:
                    raise ValueError(_SENTINEL)
                except ValueError as cause:
                    raise SourceUnavailable("provider request failed") from cause
    spans = exporter.get_finished_spans()
    assert len(spans) == 2
    for span in spans:
        assert span.status.status_code is StatusCode.ERROR
        assert span.status.description == "stage failed"
        assert span.events == ()
        assert _SENTINEL not in str(span.to_json())


def test_http_and_pollable_failures_never_return_provider_exception_text():
    app = Flask(__name__)

    def fail():
        raise SourceUnavailable(_SENTINEL)

    with app.app_context():
        response = app.make_response(run_use_case(fail))
    assert response.status_code == 502
    assert _SENTINEL not in response.get_data(as_text=True)
    assert _SENTINEL not in _failure_reason(SourceUnavailable(_SENTINEL))


def test_all_application_owned_spans_use_the_safe_boundary():
    root = Path(__file__).resolve().parents[2] / "src" / "clearcut"
    for path in root.rglob("*.py"):
        if path.name == "observability.py":
            continue
        tree = ast.parse(path.read_text())
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "start_as_current_span"
            for node in ast.walk(tree)
        ), path
