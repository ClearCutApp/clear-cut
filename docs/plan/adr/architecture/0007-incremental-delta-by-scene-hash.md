# ADR 0007: Scene-hash deltas for incremental re-analysis

Status: Accepted
Date: 2026-08-29
Amended: 2026-08-31 (Consequences)

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

Scenes hash on content rather than position: `content_hash` covers the
normalized text and nothing else, so a renumbered but unchanged scene
produces the same hash.

The join key is a separate question, and SDD Section 2 answers it
differently: scenes join across versions on `number` plus `heading`.
Renumbering a scene therefore does not merely move it, it changes its
identity. The old number leaves as REMOVED, the new one arrives as ADDED,
and the two equal hashes are never compared. Inserting a scene re-analyzes
every scene below it.

That compute cost is accepted, and clearance pays a second one beside it.
Carry-forward matches a re-extracted finding to an existing tracker item by
scene overlap, because no store holds a finding's category and text between
runs: `TrackerItem` carries neither, and Section 6 of `infrastructure.md`
defines no findings table. An asset that stays in its scene keeps its
`finding_id` and its tracker state across versions, which is the case
Section 7 phase 5 of the SDD demonstrates. An asset that moves to a
different scene does not. It arrives as a new item at BLOCKED and a human
clears it a second time, while the item it left behind stays open, flagged
for re-review, and carrying a note naming the scene it was cleared against.
Nothing is dropped and nothing is kept without saying so, and the repeated
clearance is real work.

REMOVED scenes keep their open items, because a cut scene can return in v3.

Joining on the hash first would recover some of the wasted compute, but only
for scenes renumbered and left otherwise untouched, and it would need a rule
for two scenes in one version that hash alike, since `content_hash` is not
unique within a version. Carrying a clearance across a move needs a stored
asset identity: a category and a normalized text on `TrackerItem`, the
columns behind them, and a read that joins on the pair. Neither is
specified, so neither is built. Both are recorded as known limitations.

Edits below scene granularity also cost full price; a single changed line
re-embeds and re-analyzes the whole scene.
