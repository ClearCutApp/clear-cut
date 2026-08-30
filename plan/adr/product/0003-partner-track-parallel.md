# ADR 0003: Compete in the Parallel partner track

Status: Accepted
Date: 2026-08-29

## Context

The Agentic Cinema hackathon requires Gemini plus Google Cloud Agent Builder in
every entry, together with a product or MCP server from one partner track. The
tracks are IBM, Grafana Labs, Parallel, ClickHouse, and Replit, and each track
pays $7,500, $4,500, and $3,000 for first through third place. We must pick
the track we are judged in.

## Decision

ClearCut enters the Parallel track. Parallel's Task API runs multi-hop
rights-holder research with per-claim citations and calibrated confidence, and
clearance research asks exactly the questions that API answers, such as who
owns a song, whether a trademark registration is live, and who represents a
named person. The MCP server at https://search.parallel.ai/mcp satisfies the
track's integration requirement. ClickHouse stays in the stack as the tracker's
state store because it fits that job, and Grafana Cloud observability remains
mandatory in our architecture per ADR 0008; neither choice changes the track we
enter.

## Consequences

Track judges score our Parallel usage, so the demo must show Task API research
prominently instead of burying it behind the tracker UI. That also concentrates
risk; if Parallel's API degrades during judging week, the feature the track
judges care about is the one that breaks.
