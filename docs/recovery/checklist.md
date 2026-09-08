# Recovery implementation and evidence

Statuses distinguish implemented code from verified runtime behavior. Check boxes
close only with evidence, never historical checkpoint labels. Current authority and
execution plan: [September 7 situation](situation-2026-09-07.md); reusable
[completion prompt](completion-prompt.md).

- [x] Canonical approved specification and dated situation report.
- [x] Runtime-neutral engineering guidance with historical instructions superseded.
- [x] Immutable unique upload keys and offline collision regression proof (live adapter success verified; namespace migration pending).
- [ ] Firebase identity and private workspace journey.
  Server token boundary, Firestore organization/project bootstrap and browser account UI implemented;
  offline checks and live Firestore separation verified. Real browser account journey pending.
- [ ] Named legacy owner, resumable migration, backup and rollback rehearsal.
- [ ] Firestore transactional drafts/revisions/tracker/jobs and ClickHouse outbox.
  Draft/revision CAS metadata and immutable content implemented; offline verified. Live draft CAS unverified. Tracker generations/CAS/audit/epoch, durable jobs and leased ClickHouse analytics outbox implemented/offline verified; runtime schema/indexes/Jobs, legacy envelope reconciliation and live delivery remain.
- [ ] Durable Cloud Run analysis: leases/retries/cancellation/idempotency/recovery.
  Revision-bound HTTP/client, packaged worker/dispatcher, fenced leases/heartbeat/checkpoints, retries/cancellation, immutable generation publication and human-edit rebase implemented. Offline fault tests verified; Jobs/Scheduler/indexes/IAM and actual process-restart/deployed verification remain. See durable-analysis.md.
- [ ] PDF/DOCX/Final Draft import; editor/autosave/history/conflicts and exports.
  PDF/DOCX/FDX import, editor/autosave/history/conflicts, PDF/FDX export implemented and offline verified. All three pages of Spanish/long-dialogue PDF specimen visually checked; deployed imports and Final Draft application compatibility unverified.
- [ ] Producer/writer workspace, onboarding, teams and private project management.
  Team membership/invitations, explicit assignments, rejoin-safe grants and expected-version production settings/locations implemented and verified offline. Live authenticated multi-user journey remains blocked/unverified.
- [ ] Clearance evidence/assignments/due dates/audit and permission drafts.
  Private Documents upload/list/download and immutable original preservation implemented; clearance version checks, immutable audit, evidence links, due dates, conditions, cited rights-holder research, editable PDF/TXT permission drafts, project assignee directory/picker and explicit revision-bound human reconfirmation implemented/offline verified. Live transaction verification remains.
- [ ] Fixed-revision PDF/CSV reports with documented calculations.
  Effective human overlays, fixed revision/generation/epoch, owned evidence hashes and immutable PDF/CSV bytes implemented; race, authorization, export and UI regressions verified offline. Report specimen layout inspected; deployed creation/download journey remains unverified. See reports.md.
- [ ] Mobile voice-first recorded questions, editable transcription and explicit Q&A submission.
  Mobile-first recorder, explicit transcript review and Speech V2 adapter implemented; provider formats verified live; 390px mock browser entry/visible recorder/text fallback/keyboard navigation verified, browser capture unverified.
- [ ] Notifications/activity/scoped search; complete English/Spanish and accessible UI.
  Public landing, account, navigation, reports/activity and project-list EN/ES implemented; private ClickHouse activity and analysis trends implemented/offline verified. Private notifications, per-user read marks, scoped versioned webhook queue/dispatcher and binding provisioning CLI implemented/offline verified; no destination sent. Private literal search is implemented/offline verified with fixed-revision scene links and changed-result pagination conflicts; remaining view translation and deployed checks pending.
- [x] Six-country official-source manifest, resumable ingestion CLI and 12 grounded/local-gap case definitions (107 infrastructure tests; live execution unverified).
- [ ] Execute and verify six-country ingestion and all grounded/local-gap cases; reconcile legacy corpus contents.
- [ ] Each integration: current live success and failure evidence.
- [ ] Deployed complete journey; desktop/mobile/keyboard checks.
- [ ] Release assessment against every criterion in specification.md.

September 6 targets foundation; September 7 targets full journey/durable analysis/
coverage; September 8 targets reports/voice/deployed verification and defect fixes.
Unfinished scope remains listed even if the target date is at risk.


Sponsor integration requirement: preserve substantive deployed Google Cloud, Parallel and ClickHouse use. Firestore owns transactional correctness; ClickHouse receives deduplicated analytics/history through an outbox and powers activity/trends. Sponsor presence requires current success/failure evidence, never just a logo or unused adapter.

- [x] Saved-location research through Parallel, private evidence history and local Q&A gap enforcement (offline verified; live workflow unverified).
- [x] Capture local-research provenance and explicit location coverage gaps in immutable report snapshots, with research/settings/context race guards (offline verified).
- [ ] Verify current official location evidence and deployed report capture/publication; inspect refreshed local-evidence PDF specimen.

- [x] Native bounded BigQuery adapter and committed-revision scene projection, checkpointed embeddings, freshness gaps and exact scene preview links (offline verified).
- [ ] Provision and verify scene-vector table, Firestore indexes, runtime IAM and scheduled projection; reconcile legacy committed analyses.

- [x] Inspectable additive runtime-index/Job/scoped execution-IAM/Scheduler tooling, pinned-image/secret manifest and readback/unknown-submission guards (17 offline infrastructure regressions).
- [ ] Apply real runtime configuration, data-plane IAM and schemas; activate schedules only after release prerequisites and verify actual execution.


## September 7 verified additions and current blockers

- [x] Authenticated resumable synthetic acceptance CLI and current live test contract;
  target/actor/input-bound receipts, pre-mutation intent, unknown-response stop,
  bounded polling and report provenance/download validation. Ten offline tests,
  including real Flask import/edit/CAS/revision seam. See deployed-acceptance.md.
- [x] Full backend suite after acceptance changes: 1089 passed, 31 live deselected;
  Ruff, format and mypy passed. Runtime compatibility has 26 focused passing tests
  and 43 combined runtime/acceptance/environment passing tests; no later full count claimed.
- [x] Guided producer project creation, localized tracker states/categories/search,
  landing excerpt/date localization and responsive hero. Frontend 455 tests/79 files,
  typecheck, CSS lint and production build passed; local mock browser paths inspected.
- [x] Runtime plans preserve existing secret-backed ClickHouse host/user and OTLP
  endpoint using pinned references with exclusive public/secret choice and per-job scopes.
- [x] Fresh live GCS same-name generation/byte preservation and Firestore own/cross-org/
  missing-grant isolation verified; disposable resources cleaned up.
- [ ] Firebase registration and browser auth: terms/setup pending; deployed client-config
  still 404. Old ready revision remains clearcut-00007-7np; no current-code acceptance.
- [ ] Real runtime accounts/IAM/indexes/schemas/Jobs and scheduled execution:
  no Jobs observed, Scheduler API disabled; configuration tooling is not execution proof.
- [ ] Fresh Parallel Task success after observed translated server disconnect;
  other passing adapter probes do not close all integrations or all-country grounded evaluation.
- [x] Document AI diagnostic: one scene/page 1 and expected synthetic text verified;
  heading punctuation caused the initial overstrict assertion. Exact-generation cleanup passed.
- [ ] Shared header/demo-banner and inspector EN/ES; human-readable entity-first
  findings; producer navigation cleanup; actual browser voice, desktop/mobile acceptance.

- [x] Twelve-case legal evaluation executor with direct production Vertex adapter,
  hash-verified source/URI/passage checks, frozen target/provider configuration,
  no automatic repeat after interruption and private application local-gap/state
  readback. Offline verified; real all-country execution and semantic assessment
  remain unverified. See legal-evaluation.md.
- [x] Fresh Speech `chirp_2` synthetic audio diagnostic verified actual phrase;
  browser capture and full voice-to-question journey remain unverified.
