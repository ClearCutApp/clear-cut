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
