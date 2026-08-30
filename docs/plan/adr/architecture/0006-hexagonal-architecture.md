# ADR 0006: Hexagonal architecture per AGENT.md

Status: Accepted
Date: 2026-08-29

## Context

Two target layouts contradict each other. docs/resources/Codebase-Structure.md
pastes a flat Flask app.py with templates, while .claude/AGENT.md section 2
mandates a hexagonal src/clearcut/ split into domain, application, and
adapters, wired in one place, composition.py.

## Decision

AGENT.md wins and the flat layout is superseded. domain/ holds pure models and
rules. application/ holds the use cases AnalyzeScript, EvaluateDelta,
ResolveFinding, and AnswerProjectQuestion. adapters/ holds every integration,
including Document AI, Gemini, Parallel, Vertex AI Search, BigQuery, and
ClickHouse. The anti-over-engineering rules in AGENT.md section 4 bind: no port
without a real I/O boundary, no DI containers, no event buses, no CQRS.

## Consequences

The layout carries more files than a flat app.py, and the wiring discipline
costs setup time in week one. The repayment comes when adapters get swapped or
faked in tests; AGENT.md section 5 requires hand-written fakes instead of mock
patching, and that only works when every integration sits behind an adapter
seam.
