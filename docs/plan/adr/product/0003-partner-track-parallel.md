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
named person. Parallel's Search API, called through the `parallel-web` SDK,
satisfies the track's integration requirement. ClickHouse stays in the stack as
the tracker's state store because it fits that job, and Grafana Cloud
observability remains
mandatory in our architecture per ADR 0008; neither choice changes the track
we enter.

## Consequences

Track judges score our Parallel usage, so the demo must show Task API research
prominently instead of burying it behind the tracker UI. That also concentrates
risk; if Parallel's API degrades during judging week, the feature the track
judges care about is the one that breaks.

Task API processors are slower than a live demo tolerates, with `core` at a
1.5-minute median, so the on-camera lookup runs through the Search API in
`fast` mode, inside `AnswerProjectQuestion`, while the Task API run starts at
upload. `docs/plan/infrastructure.md` section 7.1 records that split.

## Amended 2026-09-06

Both paragraphs above said MCP where they now say the Search API. The
integration requirement was recorded as satisfied by the server at
https://search.parallel.ai/mcp, and the on-camera lookup was recorded as
running through it.

Neither was true of the running system, and the amendment is what makes them
true rather than what changes the decision. An MCP server is called by an
agent, and no Agent Builder agent exists anywhere under `src/`; the only place
that URL appears in this repository is `.mcp.json`, which configures Claude
Code for the people developing ClearCut and is never loaded by the deployed
service. Citing developer tooling as the submission's runtime integration is
exactly the over-claim section 11 of `docs/plan/infrastructure.md` asks judges
to verify against the code.

What runs instead is `adapters/parallel/search.py`, an adapter over the same
`parallel-web` SDK the Task API already uses. `AnswerProjectQuestion` calls it
when the licensed corpus produced no citation for a legal question, which
`docs/plan/sdd.md` section 9.2 records is the common case. The track is
unchanged, the partner is unchanged, and the key is unchanged; only the
surface is named correctly.

The MCP servers remain in the References below. They are the path to take if
research is ever driven from an agent instead of from our own adapter, and
that is the only claim this ADR now makes about them.

## References

- API overview: https://docs.parallel.ai/getting-started/overview
- Task API quickstart: https://docs.parallel.ai/task-api/task-quickstart
- Research basis and citations:
  https://docs.parallel.ai/task-api/guides/access-research-basis
- Search API quickstart: https://docs.parallel.ai/search/search-quickstart
- MCP servers, not used at runtime: https://docs.parallel.ai/integrations/mcp/quickstart
- Worked examples: https://github.com/parallel-web/parallel-cookbook
