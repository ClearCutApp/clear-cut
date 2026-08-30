# ADR 0007: Scene-hash deltas for incremental re-analysis

Status: Accepted
Date: 2026-08-29

## Context

The legacy "Dynamic Scalability Module" promises delta evaluation between
script v1 and v2 but never specifies a delta representation, a diff
granularity, or a reconciliation rule for permissions when the underlying
scene changes. Without those three pieces, every new script version costs a
full re-analysis, and a permission negotiated against the old text has no
defined fate.

## Decision

The scene is the delta unit. Each scene stores a content hash. When script v2
arrives, only scenes whose hash changed get re-embedded and re-analyzed.
Findings on unchanged scenes carry forward, and so do permissions already
obtained. A changed scene that carried a cleared permission flags its tracker
item for human re-review; the pipeline neither keeps the clearance silently nor
drops it.

## Consequences

Scenes must hash on content rather than position. A renumbered but unchanged
scene has to produce the same hash, or every reorder looks like a full rewrite
and the incremental path buys nothing. Edits below scene granularity also cost
full price; a single changed line re-embeds and re-analyzes the whole scene.
