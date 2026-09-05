# ADR 0014: Findings are durable, and the tracker key is wrong

Status: Accepted
Date: 2026-09-05

## Decision summary

Persist findings. Re-key `tracker_items` and `script_versions`. Both changes
land together behind one destructive migration a human approves.

## Context

Two storage problems, one cause: the schema was designed for a demo that runs
once against one project.

**Findings are never persisted.** `AnalyzeScript` returns an `AnalysisReport`,
the route serializes it, and that is the only place a `Finding` has ever
existed. `TrackerStore` saves the `TrackerItem` each finding produced, but a
tracker item carries no `raw_text`, no `category`, no `page` and no citations --
it is the actionable side of a finding, not the finding. So the evidence
disappears the moment the response is sent. Reload Script Review and it renders
nothing. Open a tracker item and the panel can show its state and its contact
but not what was found, where, or under which law.

It also breaks the delta path. `EvaluateDelta` carries cleared items forward by
matching on scene overlap rather than asset identity, because asset identity
lives on the finding and the finding is gone. D37 records that limitation: an
asset that moves between scenes gets cleared twice.

**The tracker key collides across projects.** `tracker_items` is
`ReplacingMergeTree(version) ORDER BY item_id`. Item ids are `EVT-NNN`, minted
sequentially per analysis. Two projects both produce `EVT-001`. `ORDER BY
item_id` makes those the same row, and on the next background merge ClickHouse
keeps the higher version and discards the other. One project's clearance history
is gone. Nothing errors. Nothing logs. The read simply returns the other
project's item.

**Script versions collapse.** `script_versions` is
`ReplacingMergeTree(version) ORDER BY project_id`. One row survives per project,
not per version. Uploading v2 permanently replaces v1 after a merge, so the
version history the delta path is built on cannot be read back.

D77 recorded all of this on 2026-09-04. The defective DDL is still shipped, byte
for byte, on the branch that documented it.

## Decision

**A `findings` table and a `FindingStore` port,** keyed
`ORDER BY (project_id, script_id, finding_id)`. Findings are written in the same
step that writes tracker items, so a script read can serve its findings and its
highlight spans without recomputing anything.

**Re-key both existing tables.** `tracker_items` becomes
`ORDER BY (project_id, item_id)`. `script_versions` becomes
`ORDER BY (project_id, script_id)` with the `(version)` argument dropped from
the engine, because a script version is a distinct row to keep, not an older
copy to collapse. `TrackerStore.latest` takes `project_id` alongside `item_id`,
which is the port change that makes the new key reachable.

**One migration, and it drops the tables.** ClickHouse cannot re-key a
`MergeTree` in place; `ORDER BY` is part of the table's physical layout.
`infra/provision_tracker_schema.py` grows `--recreate`, `--force` and
`--dry-run`, and the destructive path requires a human to confirm, because the
deployed service holds the demo project's clearance state.

## Consequences

Script Review survives a reload, the detail panel can show its evidence, and the
delta path gets the asset identity it needs to stop clearing the same asset
twice. None of that is reachable without this.

Two projects stop destroying each other's data. This is the fix that matters
most and is least visible: nothing was failing, so nothing was going to surface
it except reading the DDL.

The migration drops every row currently in ClickHouse, including the seeded demo
project's tracker state. It is re-seedable through `infra/seed_project_bible.py`
and one analyze call, which is the reason this is affordable now and will not be
later. Doing it after real producers have data means writing a backfill instead.

Findings cost storage that grows with every analysis of every script version,
and nothing prunes them. At demo scale that is nothing. It is a real question
the first time a production company uploads a hundred drafts.

`TrackerStore.latest` changing signature touches the adapter, the port, the
fakes and every caller in one commit. It cannot be staged, because a port and
its only implementation disagreeing is a red gate rather than an intermediate
state.
