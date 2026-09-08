# ADR 0016: Production identity and durable workspace state

Status: Accepted September 6, 2026; implementation and live verification pending.

Keep Flask/React and hexagonal boundaries. Firebase verifies Google and verified
email/password identity. Firestore transactions own organization/project access,
drafts, immutable revisions, tracker mutations and jobs. ClickHouse remains history
and analytics through an outbox. Explicit project grants are required in addition
to active membership. Legacy records stay quarantined until a human identifies the
owner workspace; migration preserves IDs, records checkpoints, reconciles counts
and rehearses backup/rollback.

This amends ADR 0013: Cloud Run Jobs replace daemon threads. Persist launch intent,
lease/stage/retry/cancellation state, and idempotent results. This amends ADR 0014:
operational findings/clearance state must be transactionally bound to revisions;
ClickHouse append history cannot resolve concurrent authorization or state changes.
This amends ADR 0007: scene-hash equality alone cannot preserve legal clearance
when jurisdiction, production context or clearance conditions have changed.

Tradeoff: Firestore and job orchestration add provisioning and migration work,
but remove process-local persistence and ambiguous concurrent writes. Existing
provider adapters and analysis behavior remain reusable behind their ports.

See ../../../recovery/specification.md for release acceptance. Required runtime
provisioning and legacy ownership are recorded in the dated situation report.
