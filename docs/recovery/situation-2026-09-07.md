# ClearCut situation — September 7, 2026

ClearCut is a producer/screenwriter clearance workspace with substantial implemented
code and incomplete deployed integration evidence. The current Cloud Run service
still exposes an older contract. Local test success is not release readiness.
This snapshot supersedes September 6 status counts without deleting their history.

## Authority and actual architecture

Read [specification.md](specification.md),
[ADR 0016](../plan/adr/architecture/0016-production-recovery.md), then
[checklist.md](checklist.md). Root [AGENTS.md](../../AGENTS.md) and active session
instructions govern execution. `.claude` checkpoint labels, role prompts, topology
and planning documents are historical context; they do not require a role loop,
Claude-only tools, extra approvals, or a reduced product scope.

Keep Flask, React/Vite and inward dependencies: adapters → application → domain.
`composition.py` wires providers. Firestore owns memberships/grants, drafts,
revisions, tracker mutations and jobs. Cloud Run Jobs execute durable analysis.
ClickHouse receives deduplicated analytics/history through an outbox. GCS holds
private immutable originals, revisions, artifacts and reports. The remaining
Google, Parallel, webhook and Grafana integrations remain required by the spec.
The product is ClearCut; references to CapCut do not change its approved contract.

HEAD at inspection is `acd0fcd`, with substantial pre-existing uncommitted work.
Preserve staged, unstaged and untracked files. One writer remains the working rule.
No release, migration, schedule activation or receipt-driven approval is inferred.

## Verified current state

| Area | Evidence and remaining gap |
| --- | --- |
| Local backend | Full suite after acceptance changes: 1089 passed, 31 live deselected. Ruff/format and mypy passed. Runtime compatibility then added 14 regressions: 26 runtime tests and 43 combined runtime/acceptance/environment tests passed; no newer full-suite count is claimed here. |
| Local frontend | 455 tests in 79 files, TypeScript, CSS lint and production build passed. Large bundle warning remains. |
| Frontend behavior | Local mock browser: cinematic landing; edit/save revision/preview; analysis to tracker/inspector; text Q&A. Spanish tracker/search and guided project creation implemented. Shared header/banner and inspector translations, entity-first labels and producer navigation still need polish. |
| Deployed service | Ready revision `clearcut-00007-7np`, older image digest prefix `d520359`. Health returns 200/live; `/api/client-config` returns 404. This does not serve the new authenticated client contract. |
| Firebase | Admin project/config probes returned 404. Browser registration remains at terms acceptance; account setup and authenticated browser journey are not proven. |
| Runtime | No Cloud Run Jobs observed; Scheduler API disabled; only default Compute service account observed. Firestore is native in `us-central1`, deletion protection enabled, PITR disabled. Seven existing provider secret references observed; no secret values read. Runtime provisioning tools exist, but real identities/IAM, schemas, indexes and Job execution remain. Metadata probes found `analytics_events` and `analysis_scene_vectors` absent; existing `lore_vectors` present. |
| Gemini / Vertex / Parallel | Fresh Gemini extraction/usage, Vertex Argentina citations and missing-corpus Korea gap, and Parallel Search passed. Parallel Task ended in server disconnect translated to `ResearchUnavailable`; no retry and no fresh Task success. These adapter probes do not prove all-country/application coverage. |
| Originals / access | Fresh live GCS same-name upload proof verified distinct generations and exact original bytes; live Firestore own-project access, cross-organization denial and missing-grant denial passed. Two tests completed in 29.22 seconds with cleanup. |
| Speech | Actual `chirp_2` in `us-central1` transcribed a validated 2.68-second synthetic WAV correctly in 2.96 seconds; diagnostic `/tmp/clearcut-speech-diagnostic.json`. Actual browser capture remains unverified. |
| Document AI | Diagnostic verified one scene on page 1 with the expected synthetic text. OCR omitted a heading hyphen, exposing an overstrict first probe assertion. Exact-generation cleanup passed; diagnostic artifact `/tmp/clearcut-docai-diagnostic.json`. |
| Deployed acceptance harness | New authenticated, target/actor/input-bound resumable CLI replaces obsolete unauthenticated synchronous test. Ten offline tests include real Flask PDF import/edit/CAS/revision seam, interrupted mutation, polling resume, binding and corrupted revision checks. Not executed against the new deployment. |
| Runtime manifest | ClickHouse host/user and OTLP endpoint can preserve pinned Secret Manager references or use public values exclusively. Per-job minimal distribution is tested; configuration was not applied. |

## Discrepancies resolved

Historical status mixed code completion, mock behavior and live proof. The checklist
now keeps those separate. The old end-to-end test submitted unauthenticated
`gcs_uri` with synchronous expectations; the current contract requires a verified
identity, private project, saved revision and asynchronous 202/poll/readback.
See [deployed-acceptance.md](deployed-acceptance.md).

Historical runtime plans forced some existing secret-backed settings into public
environment fields. The manifest now preserves numeric secret references without
reading values. See [runtime-provisioning.md](runtime-provisioning.md).

The app follows the supplied navy/emerald producer references while showing actual
available fields and metrics. No poster art, team counts or clearance progress is
invented for project responses that do not carry them. Existing editor supports
PDF/DOCX/FDX import; the older mock analysis form is not live revision acceptance.

## Completion plan

1. Finish real account registration/configuration and prepare dedicated identities,
   least-privilege data access, additive schemas/indexes and pinned runtime plans.
   Deploy current code only through authorized operations. Keep recurring schedules
   separate until prerequisites and execution evidence exist.
2. Finish the six-country legal evaluation executor and reconcile ingestion evidence.
   Verify national Vertex provenance independently of Parallel fallback, and local
   gap behavior through the application. Structural citation validation does not
   establish legal correctness; record semantic assessment separately.
3. Run the authenticated synthetic deployed journey with durable receipts, then
   browser desktop/mobile/keyboard acceptance. Prove worker restart, cancellation,
   retry and duplicate suppression with real persisted jobs; mocks cannot close it.
4. Close shared-shell/inspector translations and entity-first usability; verify real
   voice capture, team isolation, evidence/report download and accessible navigation.
5. Verify current application-level success and failure for every required provider,
   analytics/outbox, webhook and telemetry receiver. Rehearse backup, explicit-owner
   migration, reconciliation and rollback before assessing release criteria.

Continue independent code/evidence work while account or external setup is blocked.
Do not omit integrations or replace required execution with a plan. Treat unknown
mutations as reconciliation work, never as permission to retry blindly.

## Handoff

Use [completion-prompt.md](completion-prompt.md) for a runtime-neutral continuation.
Keep this dated snapshot immutable in meaning; append new dated evidence or update
[checklist.md](checklist.md) rather than silently turning unverified checks into passes.
