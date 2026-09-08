# Fixed clearance reports and human confirmation

Report creation captures one committed analysis and its saved screenplay revision.
The browser sends the displayed analysis/revision, generation and clearance epoch.
The service reads effective human overrides, recorded item versions, findings,
revision bindings, cited research, original evidence metadata and hashes. It also
records actor/time, language, formula/template versions, coverage gaps and whether
a newer draft existed at capture. A report is not a legal opinion.

Snapshot JSON and PDF/CSV derivatives are immutable GCS objects. A final Firestore
transaction rechecks membership, explicit producer grant, generation, epoch and
analysis/revision identity before publishing metadata and an outbox event. A race
returns 409; staged objects remain invisible. Later downloads reauthorize the
project and read the recorded derivative bytes with integrity checks. They never
render mutable latest clearances. Old reports remain unchanged after later edits.

`clearance-counts-v1` uses every retained tracker item as the denominator, including
items no longer detected. Confirmed cleared means `CLEARED && !needs_review`.
Needs-review takes precedence over the three recorded states, producing exclusive
counts. Confirmed percentage is rounded to one decimal; an empty report is 0%.
Present, no-longer-detected and unknown-binding counts are recorded separately.
This is distinct from the legacy 0/50/100 weighted workflow-progress metric.

CSV quotes every cell and prefixes formula-triggering text with an apostrophe,
including leading whitespace/control variants. Canonical numeric fields remain
numeric and canonical snapshot text is unchanged. PDF text is escaped, uses
embedded redistributable ReportLab Bitstream Vera fonts, and spells unsupported
glyphs as Unicode names instead of silently losing them. Ordinary items stay
together; oversized items split with item identity in the page footer. Both EN/ES
reports retain the original wording of user and provider evidence.

Human reconfirmation requires an explicit acknowledgement that permission,
evidence and conditions apply to the displayed analyzed revision. The application
validates the immutable current binding, including presence and applicability
signature; the write transaction checks the same generation and expected item
version. It records actor, revision and generation in an immutable audit event,
sets CLEARED and removes needs-review. Removed or unknown bindings cannot be
reconfirmed against the new revision. Research and ordinary state changes never
remove review flags. Changing cleared evidence or permission conditions flags
the item for review again; an ordinary note edit does not.

Offline evidence covers 175-item PDF/CSV totals, Unicode and markup, formula
injection, immutable effective overlays, evidence hashes, render/publication
races, private HTTP resources, stale revision/item confirmation and late browser
responses after project switches. Parent visual checks found and prompted fixes
for ordinary-item pagination and unsupported glyphs. New runtime Firestore/GCS
report transactions and the deployed authenticated journey remain unverified.

## Captured production-location research

Template `clearance-report-v2` freezes the latest 50 private local-research records,
including record identity, actor/date, source citations, question, settings version
and a SHA-256 of the captured research set. It records the research epoch and current
production settings version. Research creation increments the epoch transactionally;
the final report publication also checks this epoch, settings version and production
context hash. A research/settings change during rendering therefore returns 409.
Existing report bytes and older template versions remain unchanged.

Each selected location is labeled either evidence recorded or coverage gap. Only
cited evidence for that exact location and current settings version satisfies the
recorded-evidence label; it never implies a permit, a known fee, complete coverage
or legal clearance. No selected locations is itself an explicit gap. The recent-50
history window is printed; older evidence may be omitted and cannot silently close
a gap. PDF includes dated source references and bounded quoted excerpts, with
explicit excerpt labels when shortened; full quotations remain in the immutable
snapshot. CSV adds captured research IDs, missing-location labels and the shared
research-set hash to each clearance row. All untrusted CSV values retain formula
neutralization, including location text.

Offline regressions exercise research/settings/context publication races, immutable
research provenance, location gaps, transactional capture and both rendered exports.
The new local-evidence PDF fixture is available as
`tests.unit.adapters.test_report_export.local_report_snapshot()`; refreshed visual
inspection and deployed transaction proof remain separate release evidence.
