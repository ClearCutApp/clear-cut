# ClearCut production specification

Approved recovery scope, September 6, 2026. Target readiness: September 8,
ahead of September 9. This document supersedes conflicting MVP assumptions in
`docs/plan/sdd.md`, historical checkpoint labels, and runtime-specific workflows.
The date is a delivery constraint, not proof of readiness.

## Product contract

Producers and screenwriters share private projects in organizations. Firebase
Authentication provides Google and verified email/password identity; Flask verifies
tokens. Server-side organization membership and explicit project grants control
access. Organization membership alone exposes no private project.

Owners/admins manage membership; producers manage assigned projects and clearances;
writers edit assigned screenplays and bible; viewers read assigned projects.
Revocation takes effect on the next request. Cross-organization resource probes
return no private data. Legacy records remain quarantined until a named owner
workspace is selected and a resumable migration reconciles preserved IDs.

Firestore is authoritative for memberships, access, drafts, revisions, tracker
changes and jobs. Transactions enforce expected-version writes. ClickHouse receives
analytics/history through an outbox; it cannot authorize access or arbitrate edits.
Cloud Run Jobs execute durable analysis with persisted launch intent, leases,
stages, retries, cancellation and terminal failures. Re-delivery is idempotent.

## Required journeys

- Import PDF, DOCX and Final Draft with immutable originals under unique
  organization/project/file keys. Clients use authorized file IDs, never storage URIs.
- Edit structured Tiptap screenplays with stable scene/block IDs, autosave,
  immutable version history and explicit concurrent-write conflict recovery.
  Analyze a saved revision; anchor findings and citations to it. Edits mark old
  findings stale. Retain human clearance only while scene and conditions still apply.
  Export PDF and Final Draft. Live simultaneous co-editing is outside this release.
- Navigate onboarding, overview, script review, clearances, documents, activity,
  reports, teams, notifications and scoped search.
- Assign clearance work with evidence, attachments, due dates, cited rights-holder
  research and audited status changes. Generate editable permission-request drafts
  and downloadable documents. Outreach remains human-reviewed; mailbox sending is
  outside this release. Research and AI risk never imply human-confirmed clearance.
- Export PDF/CSV reports from fixed revision and recorded clearance state.
  Document score/count calculations; never fabricate metrics.
- Record Q&A voice through Google Speech-to-Text, edit transcription, then submit.

## Integrations and legal coverage

Preserve Flask, React/Vite, hexagonal boundaries and GCP deployment. Verify actual
application calls to Document AI, GCS, Gemini extraction/continuity, Vertex Search,
BigQuery lore, Parallel Task/Search, ClickHouse, webhooks and Grafana/OpenTelemetry.
Centralize model IDs, deadlines, bounded retries and provider error translation.
Developer MCP connectivity provides no deployed-integration evidence.

Launch countries: Argentina, Mexico, Spain, Colombia, United States and Canada.
Each needs a dated official-source manifest with jurisdiction, subjects, provenance
and ingestion status, plus grounded evaluation cases. Research local requirements
for selected production locations. Unsupported local questions expose coverage gaps.

## Interface contract

Maintain OpenAPI and frontend client with identity context, organizations,
memberships/invitations, project grants, file IDs, drafts/revisions, documents,
reports, notifications, expected-version writes and progress/cancellation polling.

English/Spanish, responsive and keyboard-accessible. Respect reduced motion.
Use near-black/navy surfaces, emerald actions, readable screenplay pages,
persistent navigation and contextual inspection. Landing includes cinematic imagery,
product promise, workflow demonstration and signup. Primary controls must work;
empty/loading/error states must explain the next available action.

## Release evidence

Release requires deployed browser proof of upload → edit → save revision → analyze
→ inspect citations → resolve → attach evidence → export report. Demonstrate
cross-organization denial, same-name preservation, concurrent-save conflicts,
worker recovery and duplicate-result suppression. Every provider needs dated
success and failure evidence. Skipped checks remain unverified. Rehearse migration,
backup reconciliation and rollback; exclude screenplay text and credentials from
telemetry. Verify desktop/mobile and keyboard journeys.

## Mobile voice-first workflow (2026-09-06 steering)

Mobile project entry foregrounds recorded questions in current project/scene context. Recording, stop, cancel, upload, transcription and recoverable errors are explicit. The user edits transcription and submits separately; voice never infers clearance mutations. Text fallback, readable citations and reachable Script/Clearances navigation remain available with safe-area padding and keyboard support. Desktop retains the screenplay workspace.

Sponsor integration requirement: preserve substantive deployed Google Cloud, Parallel and ClickHouse use. Firestore owns transactional correctness; ClickHouse receives deduplicated analytics/history through an outbox and powers activity/trends. Sponsor presence requires current success/failure evidence, never just a logo or unused adapter.
