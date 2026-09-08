# ADR 0009: React SPA frontend in web/

Status: Accepted
Date: 2026-08-29

## Context

The legacy UI is a Tailwind index.html rendered from Flask templates, which
mixes presentation into the backend. The product needs a Grammarly-style
inline-findings overlay on the script, a live tracker dashboard, and a Q&A
panel, and template rendering fights all three.

## Decision

The frontend is a React + Vite + Tailwind SPA in web/ at the repo root,
outside src/clearcut/. The API serves JSON only. Components follow atomic
design; container components own data fetching and state, presentational
components stay pure. One typed API client module is the single point of
contact with the backend. The SPA exposes three surfaces, ScriptView,
TrackerDashboard, and ProjectQA.

## Consequences

The repo gains a second toolchain, Node, and a build step before every deploy.
In exchange, UI churn during demo week never touches the clearance core; a
component rewrite cannot break an adapter.

## Amendment 2026-09-08

Two things this record said were not true of the code, for different reasons.

**Tailwind now is.** The dependency was never added: CP-011 deferred it as
config with nothing exercising it, and reaffirmed that ruling twice, leaving a
Backlog entry that waited for "the first class that a test actually exercises".
The trigger never fired, and the gap filled with a second styling system --
`tokens.css` asserting that every color is named there and nowhere else, and
`landing.css` answering with forty literals and a different brand green. The UI
rebuild is the checkpoint that fires the trigger, so the code came to the
record rather than the record to the code. Tailwind v4 is installed, imported
by layer without preflight, and `tokens.css` is the project's `@theme` in two
named layers, `brand` and `product`. The decision line above stands as written.

**Three surfaces became twenty views.** `ScriptView` survives, `ProjectQA` is
`AskView`, and `TrackerDashboard` does not exist -- the tracker is
`OverviewView` over `TrackerTable`. The count is the part that aged: the SPA
routes twenty views, twelve of them under `/projects/:projectId`. The index
recorded this as "six routed views", which was already stale when written.

Atomic design, the pure-presentational rule, and the single typed API client
are unchanged and enforced: `web/src/architecture.test.ts` fails the build if an
atom imports from `src/api/`, or if any module other than `api/client.ts` names
an `/api/` path.
