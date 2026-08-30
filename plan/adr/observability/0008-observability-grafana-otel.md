# ADR 0008: OpenTelemetry to Grafana Cloud

Status: Accepted
Date: 2026-08-29

## Context

An agentic pipeline with five external services fails in ways a log line does
not explain. The team decided observability is a launch requirement rather
than an add-on.

## Decision

The pipeline carries OpenTelemetry instrumentation exported to Grafana Cloud
via OTLP. Instrumentation lives in composition.py and the adapters, never in
domain/. Each pipeline stage gets one span, covering ingest, extract, ground,
research, and track. Metrics cover per-stage latency, tokens per Gemini call,
findings by severity, and tracker items by state. The grafana/mcp-grafana MCP
server stays a candidate for letting the Q&A agent read operational state; we
evaluate it after the core pipeline works.

## Consequences

Every adapter carries a small instrumentation cost, and a Grafana Cloud
account becomes part of environment setup for every developer. In return,
one trace per pipeline run carries the five stage spans, so a failing
external call names its stage instead of hiding in a log line.
