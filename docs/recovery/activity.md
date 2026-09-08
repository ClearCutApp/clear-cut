# ClickHouse activity and analysis trends

Firestore commits operational changes and immutable minimized outbox envelopes in
the same transaction. Project creation, saved revisions, documents, human
clearance changes, published analysis and reports supply organization/project,
stable event identity, source version, timestamp, schema version and payload hash.
Analysis events freeze exclusive clearance counts at publication. No screenplay,
contact, permission draft, note, evidence bytes or provider exception is projected.

The packaged `python -m clearcut.activity_dispatcher` performs a bounded scheduled
delivery pass. Firestore claims use 90-second leases and monotonically increasing
fences. ClickHouse accepts immutable events before Firestore acknowledges them.
A lost acknowledgement can insert the same row again; read queries group by
organization/project/event before paging and check payload variants. They never
depend on background merges for counts, and conflicting identities fail closed.
Five attempts use bounded exponential backoff; exhausted events stay failed.
Invalid envelopes are quarantined when claimed. Delivery is at least once.

The project Activity page reads ClickHouse through the normal membership plus
explicit project-grant boundary. It displays recorded history and the last 50
analysis snapshots; history pages use timestamp plus event-ID cursors. Trends
describe counts at analysis completion, not today's mutable clearance state.
Unknown historical counts display a coverage gap rather than invented zeroes.
Recent changes may not have reached the projection yet. This is substantive
ClickHouse history/analytics alongside Google Cloud transactional infrastructure
and Parallel research; it is not a second operational authority.

## Provisioning and evidence

Inspect the additive schema without credentials:

```sh
.venv/bin/python infra/provision_activity_schema.py
```

After authorized provisioning, `--apply` executes only
`CREATE TABLE IF NOT EXISTS analytics_events`; it never drops legacy tables.
Use a Cloud Run Job with the existing image and explicit command `python`,
arguments `-m clearcut.activity_dispatcher`, one task and no platform retries.
Schedule a bounded pass once per minute using authenticated Cloud Scheduler.
The Job needs GOOGLE_CLOUD_PROJECT and the existing CLICKHOUSE_HOST/USER/PASSWORD
secret bindings plus Firestore write permissions scoped to the application.
ClickHouse uses 10-second connect and 30-second request budgets, no query retries.
Provision Firestore outbox collection indexes for state + available_at and
state + lease_until. This runtime, schema and these indexes have **not** been deployed.

Pre-existing outbox documents without available_at are not discoverable through
the new indexed due query. Reconciliation must inspect their immutable envelope:
complete, valid events can receive an initial due timestamp; incomplete legacy
events require explicit ownership and immutable source evidence or quarantine.
Never guess organization/time or reconstruct an event from mutable latest state.
This is a migration prerequisite, not silent successful delivery.

Offline checks cover accepted insertion with lost acknowledgement, identical
redelivery, fence rejection, retry exhaustion, malformed/hash-altered payloads,
query grouping and parameter scope, private HTTP access and late browser responses.
Real ClickHouse SQL execution, Firestore lease races, scheduler operation and
post-insert crash recovery remain unverified. Existing live ClickHouse job-adapter
evidence is separate and does not verify this new analytics table.
