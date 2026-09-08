# Committed revision lore in BigQuery

Scene indexing now has its own durable outbox. The analysis publication
transaction creates the immutable `lore_outbox/{analysis_id}` intent alongside the
committed result. Staged or cancelled results never enqueue scene indexing.
Google Cloud performs embedding and storage; the existing ClickHouse activity
outbox remains independent and substantive.

The packaged `python -m clearcut.lore_dispatcher` command processes up to 16
batches, stopping before starting another batch after four minutes. Each batch
contains up to eight excerpts of at most 1900 UTF-8 bytes. Every character of every
scene is included; no source text is truncated. Embedding auto-truncation is
disabled. The original immutable analysis retains complete scenes and block
anchors, and each excerpt records its scene identity and starting character.

The dispatcher holds a fenced 90-second lease with a 20-second heartbeat. It saves
the embedding result in immutable GCS storage before loading BigQuery. A lost
BigQuery response retries the same saved vectors and deterministic load-job ID;
conflict recovery retrieves that job instead of starting another logical load.
Reads deduplicate logical document IDs before ranking. Five failed attempts at
the same cursor produce a terminal failure; advancing a completed batch resets
the attempt count for the next cursor. Failed/expired work never marks the index
ready. Concurrent newer analysis publication is checked again before Q&A returns
scene evidence.

Q&A uses only the completed projection for the current committed analysis and
its frozen embedding model. Until then, it explicitly reports unavailable scene
indexing. It does not substitute an earlier revision's scenes. Returned excerpts
link to the exact saved revision and stable scene in the editor; opening that
link changes only the preview, not the draft. Editable bible facts remain in the
existing project-scoped lore table.

The native BigQuery adapter uses explicit request/poll timeouts, zero SDK retries,
parameterized project/organization/analysis/revision filters, and a one-billion
byte query billing ceiling. The default `bigquery_timeout` is 30 seconds and is
part of `CLEARCUT_PROVIDER_OPTIONS`. Query result pagination receives that SDK
timeout too. The new adapter replaces the prior helper's unbounded query/load
waits; new loads require pre-provisioned tables and never silently create them.

## Provisioning and verification still required

Print the additive table DDL without making network calls:

```sh
.venv/bin/python infra/provision_scene_lore.py --project clearcut-hack
```

After authorization, append `--apply` to create
`clearcut.analysis_scene_vectors` in the existing regional dataset. Verify the
resulting schema and runtime read/write IAM. Create Firestore composite indexes
for `lore_outbox(state, available_at)` and `lore_outbox(state, lease_until)` with
ascending order. Deploy a separate scheduled Cloud Run Job using the application
image, command `python`, arguments `-m,clearcut.lore_dispatcher`, one task and
platform retries disabled. It requires the configured project and intake bucket,
Firestore access, GCS artifact access, Vertex embedding access and BigQuery
dataset/job permissions. Scheduler invokes the job through its scoped service
identity. Keep the job timeout above the configured maximum individual call and
batch duration; the four-minute dispatch window never interrupts an in-flight
provider call or claims that it did.

No table, index, scheduler or projection job was deployed at this checkpoint.
Offline tests prove replay/checkpoint behavior, Unicode completeness, stale
fences, publication gating, exact revision links and freshness races. They do not
prove real BigQuery SQL execution, emulator transactions, process termination
recovery, deployed IAM or index throughput. Earlier live BigQuery checks remain
evidence for the previous adapter only. Legacy committed analyses without an
outbox intent show an indexing gap until explicit migration/reconciliation.
