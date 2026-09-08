# ClearCut situation: September 6, 2026

Production readiness remains unproven. September 8 is the delivery target, not a
verified forecast. Existing staged Parallel changes are preserved. Baseline before
recovery: 838 backend and 406 frontend tests, frontend typecheck/build passed.

| Area | Current status | Evidence and remaining work |
|---|---|---|
| Accounts/private workspaces | Implemented foundation | Firebase token boundary, Firestore membership plus explicit project grants, browser account/onboarding routes; live auth blocked by Firebase terms |
| Teams/settings/locations | Implemented, offline verified | Email-bound invitations, membership versions, rejoin-safe private grants, project assignments, assignee picker and production-location settings; deployed multi-user verification remains |
| Operational state | Implemented core, live verification pending | Firestore projects/access/drafts/revisions/tracker/jobs, committed manifests and leased ClickHouse analytics outbox; new runtime provisioning and legacy reconciliation remain |
| Original uploads | Verified adapter behavior | UUID/create-only GCS keys and owned file references; same-name live byte/generation check passed; organization-key migration remains |
| Editor/revisions | Implemented, offline verified | Tiptap stable scene/block IDs, serialized expected-version autosave, local conflict recovery, immutable revision history; real draft CAS and deployed browser verification pending |
| Imports/exports | Implemented, offline verified | Structured PDF/DOCX/FDX import preserves originals; saved-revision PDF/FDX downloads; three-page PDF layout inspected; live and Final Draft application compatibility unverified |
| Voice/mobile | Implemented, verification in progress | Mobile project entry prioritizes recorder; transcript review precedes explicit question; Speech V2 and safe-area navigation implemented |
| Durable analysis | Implemented, offline verified | Revision-bound queue, packaged worker/dispatcher, lease heartbeat/checkpoints, bounded retries/cancellation, immutable generation publication and human-edit rebase; new cloud runtime provisioning and deployed fault verification remain |
| Clearances/documents/reports | Implemented core, offline verified | Private documents, evidence links, due dates, conditions, research citations, audit, permission downloads, explicit revision reconfirmation and immutable PDF/CSV reports; active-project assignment UI implemented; live transaction verification remains |
| Legal coverage | Ingestion tool and cases implemented, offline verified | 19 official texts, immutable source/provenance hashes, resumable import/readback and 12 national/local-gap cases; live ingestion and evaluations remain unverified |
| Notifications | Implemented, offline verified | Project-private attention records/read marks, explicit versioned destination binding, bounded fenced delivery and fail-closed global webhook; no receiver delivery or Job provisioned |
| Migration/rollback | Blocked | Explicit legacy owner, backups, reconciliation and rehearsal required |
| Release acceptance | Unverified | No new production deployment; complete authenticated journey, mobile capture and keyboard acceptance not proven |

## Verification evidence

Latest combined checkpoint: **1062 backend tests passed** (31 live tests deselected),
**453 frontend tests across 79 files**, full mypy over 317 files, Ruff/format over
318 files, TypeScript, production build and workspace/activity/report/clearance OpenAPI parity.
CSS lint passed at the preceding report checkpoint; no CSS changed in activity.
All three screenplay PDF pages and both permission-request PDF pages were rendered
and visually inspected: Spanish accents, long text, conditions and footers are readable.
Offline tests do not constitute live provider or deployed browser evidence.

Production clearance writes require expected versions and recheck membership/grants
inside the Firestore transaction. Current state, actor/version audit, clearance epoch
and minimized ClickHouse outbox events commit together; identical system replay is
idempotent. Evidence and assignment references are validated before writes. Adding
evidence or editing a request never changes clearance status. Legacy ClickHouse
replacing rows are surviving baselines, not complete audit history. Live clearance
transactions/outbox delivery remain live-unverified. Explicit revision-bound human
reconfirmation is implemented and tested offline, including generation/item races.
Fixed reports capture effective overlays and owned evidence hashes, publish only
after final generation/epoch/access checks, and retain immutable PDF/CSV bytes.
See reports.md for counting rules and the deployed verification boundary.

The coordinator inspected desktop landing/signup/mock analysis and actual 390×844
mobile project entry, visible recorder, text-question fallback, keyboard navigation,
immutable revision preview and clearance state/history updates. These are **mock
browser proofs**. Actual microphone capture remains unverified. Browser import opened
a file chooser but file assignment was not permitted; import remains browser-unverified.
The observed modal/navigation stacking and focus-restoration defects were fixed
and verified at 375×667, including Escape returning focus after a row changed groups.
Complete English/Spanish coverage is pending.
Public landing image provenance is recorded in image-provenance.md.

Current live evidence supplied by the recovery verifier:

- Parallel Search, Parallel Task, Gemini extraction, Vertex Argentina citations and
  absent-corpus jurisdiction: five tests passed in 72.56 seconds.
- Old deployed service health: HTTP 200/live; this does not verify new code.
- GCS same-name immutable originals: unique keys, generation and bytes verified;
  disposable objects cleaned up. Document AI parsed two anchored synthetic scenes.
- Firestore membership/project foundation: two disposable organizations/projects,
  atomic grants/index/outbox, own reads, cross-organization denial and membership-only
  admin denial verified. All 15 created documents removed and absence confirmed.
- ClickHouse disposable analysis job round-trip and wrong-project denial passed;
  exact-row cleanup confirmed. BigQuery empty-project embedding/search/facts passed;
  write round-trip was not repeated.
- Speech V2 chirp_2/us-central1: English FLAC SDK/REST, Spanish es-419 FLAC/WebM Opus/
  MP4 AAC and malformed-input failure verified. Actual browser microphone capture
  remains unverified; mock transcription is explicitly unavailable, never fabricated.
- Draft CAS live probe remains **unverified**. Initial sandbox attempt was stopped
  with zero probe documents/blobs found. The later escalated probe approval did not
  complete; there is no execution evidence and the outcome is unknown. No retry
  was attempted.
  Separate bucket/IAM/anonymous-Firestore checks produced no evidence. Further cloud
  probes require renewed authorization.

## Provisioning blockers and next action

Firebase, Identity Toolkit, Firestore and Speech APIs are enabled. Firestore
`(default)` is native STANDARD/us-central1 with deletion protection. PITR, backups,
runtime IAM and rollback remain unverified. No legacy data was assigned or migrated.

Firebase registration failed with audit status 7: **Firebase Tos Not Accepted**.
The user must accept Firebase terms before project registration and web-app/provider
configuration can proceed. No terms were accepted on the user's behalf and no
registration retry was attempted. Browser login/email delivery/token-revocation
acceptance remains unverified.

The deployment already supplies SCRIPTS_INTAKE_BUCKET and NOTIFY_WEBHOOK_URL; their
absence locally is not a production provisioning claim. Grafana readback credentials
are absent locally; webhook delivery was not sent. Never infer integrations from
MCP developer tools or historical labels.

Privacy verification reproduced then eliminated provider/question text in API errors
and OpenTelemetry exception chains. App-owned spans now retain safe failure status
and metrics; pollable job errors are sanitized. Three local sentinel probes passed.

Durable analysis is now wired for live saved revisions. Offline verification includes
701-item generations with maximum Unicode details, incomplete/cancelled/fenced
publication, human-edit rebase without repeated provider work and ambiguous Parallel
submission recovery. The coordinator's independent verifier reran 18 fault cases.
Additional independent offline HTTP checks verified private denial for other-org
owners and same-org unassigned admins, authorized queue/poll/cancel behavior, and
positive committed manifest readback with exact revision/anchors/findings. Staged
generation reads were denied and corrupted artifact content rejected.
Actual process restart and deployed worker/scheduler/IAM/index operation remain unverified;
see durable-analysis.md for configuration and evidence boundaries.

ClickHouse outbox and private activity/trends are implemented and verified offline;
new schema/lease/SQL/scheduler live proof remains. See activity.md.

Team/private assignments and production locations are implemented; see workspaces.md.
Next: authorized live ingestion/evaluations, provider budgets,
notifications/search and migration/release gates.
See checklist.md for every release criterion. No interim production deployment or
product-ready claim is authorized by these test results.

Legal ingestion tooling checkpoint: 107 infrastructure tests passed; full mypy
checked 280 files and Ruff formatting checked 281 files. No cloud import ran.
See [the ingestion runbook](legal-ingestion.md) for exact commands and evidence states.

Project-local research is implemented with saved-location/version binding,
transactional publication, official quoted sources, explicit coverage gaps and
private UI history. Local Q&A requires matching recorded evidence and does not
infer local permission from national statutes. Nine targeted backend tests and
two frontend research tests pass; two of those backend regressions were added
after the 988-test combined run. Provider calls and deployed local research remain
unverified. Matching currently uses the exact normalized question; different
questions require fresh explicit research. History displays the latest 50 records.

Provider configuration now freezes validated models and supported operation
budgets into queued jobs, disables nested SDK retries, and translates GenAI
transport timeouts into sanitized unavailable errors. Tests verify milliseconds
and the actual regional embedding client. Native bounded BigQuery queries and
loads remain the next integration step; no new live provider checks were run.

BigQuery native reads/loads and committed-analysis scene projection are implemented
and offline verified. Publication atomically enqueues a separate fenced outbox;
Unicode-complete byte-bounded excerpts and checkpointed vectors resume safely.
Q&A discloses index freshness and opens exact immutable revision/scene previews.
The scene table, indexes and scheduled job remain unprovisioned; live SQL, real
worker recovery and throughput remain unverified. See lore-projection.md.

Private notification recording, history/read UI and scoped delivery are implemented.
Sixteen new offline regressions cover authorization, content exclusion, versioned
destination revocation, lease retries and provisioning transactions. A real receiver,
Firestore query indexes, Job/Scheduler and delivery evidence remain unverified.
See notifications.md. No webhook was sent by this work.

Private literal search now covers the latest saved screenplay revision, current
clearance fields, all document-name pages and the latest 50 local-research records.
Queries remain in POST bodies; results carry revision/scene references, bounded
matching excerpts and a result-set fingerprint cursor. Changed results reject
continuation rather than mixing pages. Six backend and two UI regressions verify
accent matching, no regex execution, 175 matches without truncation, cross-project
denial, source failure, query retention and late-response isolation. Unsaved drafts,
document contents and older revisions are explicitly outside this search view.

Report template v2 now captures recent local-research provenance and its content
hash, exact-location evidence/gap labels, settings version and research epoch.
Final publication rejects research/settings/context changes; research creation
increments its epoch atomically. Six new backend regressions cover fixed evidence,
races, CSV/PDF provenance and transactional capture. Full checkpoint: 1045 backend
tests and 453 frontend tests; mypy312, Ruff/format313, TypeScript/build and diff
checks pass. Refreshed local-evidence PDF visual inspection and all deployed
research/report transactions remain unverified.

Runtime infrastructure tooling now prepares five packaged Job configurations,
eight additive queue indexes, job-scoped execution roles and four explicit
schedule activations. Default plans make no cloud calls and contain only public
environment values plus numeric secret references. Readback, existing-resource
ownership, unknown index-submission receipts, activation preconditions and
idempotence are covered by 17 new offline tests. All 1062 backend tests pass;
frontend remains unchanged from the 453-test checkpoint. Full mypy317 and
Ruff/format318 pass. No recovery Job, index, schedule or IAM binding was applied.
See runtime-provisioning.md.
