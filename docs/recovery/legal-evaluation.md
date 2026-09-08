# Execute the twelve legal coverage cases

The evaluator collects actual national Vertex evidence and deployed local-gap
behavior. `structural_verified` means provenance, preserved passage and protocol
checks passed. It never means legal correctness or permission to film.

```sh
.venv/bin/python -m infra.evaluate_legal_coverage
```

The default prints all twelve cases without network calls. Execute one case per
invocation using an existing hash-verified ingestion directory:

```sh
.venv/bin/python -m infra.evaluate_legal_coverage --execute \
  --case ar-national --target https://DEPLOYED_ORIGIN \
  --ingestion-directory /tmp/clearcut-legal-ingestion \
  --directory /tmp/clearcut-legal-evaluation
```

National execution uses the production `VertexSearchGrounding` adapter directly;
Parallel fallback is not called. Set `GOOGLE_CLOUD_PROJECT`,
`VERTEX_SEARCH_DATA_STORE_ID`, `GEMINI_MODEL`, `GEMINI_MODEL_LITE` and optional
`CLEARCUT_PROVIDER_OPTIONS` to the actual production configuration. The complete
validated model/deadline configuration is frozen in the receipt. GenAI uses the
production timeout converted to milliseconds, one SDK attempt and an explicitly
closed client. National evaluation does not require Firebase or application access.

The ingestion receipt must say `imported_readback_verified`, match the exact source
manifest and data-store target, and retain every `.original` and `.txt` file with
matching SHA-256. A GCS citation maps through its ingested document URI to the
original official URL. Every citation must match that jurisdiction and a preserved
passage of at least 40 normalized characters; at least one must match the case's
expected official source. A correct URL with an invented quotation fails. Truncated
or transformed quotations that cannot be matched remain structurally unverified;
do not weaken matching to manufacture a pass.

## Local application cases

Prepare six explicitly synthetic private projects with their case-specific
jurisdiction and saved production locations from
[the case manifest](legal-evaluation-cases-2026-09-06.json). Projects must have no
recorded local research. The evaluator does not create projects or modify settings.
Record all six bindings in a private JSON file, for example:

```json
{
  "ar-local-gap": {"project_id": "ACTUAL_PROJECT_ID", "title": "Synthetic legal evaluation AR run"},
  "mx-local-gap": {"project_id": "ACTUAL_PROJECT_ID", "title": "Synthetic legal evaluation MX run"},
  "es-local-gap": {"project_id": "ACTUAL_PROJECT_ID", "title": "Synthetic legal evaluation ES run"},
  "co-local-gap": {"project_id": "ACTUAL_PROJECT_ID", "title": "Synthetic legal evaluation CO run"},
  "us-local-gap": {"project_id": "ACTUAL_PROJECT_ID", "title": "Synthetic legal evaluation US run"},
  "ca-local-gap": {"project_id": "ACTUAL_PROJECT_ID", "title": "Synthetic legal evaluation CA run"}
}
```

Pass `--local-bindings FILE` with `--case ar-local-gap` and the same remaining
arguments. Supply a fresh verified Firebase ID token through
`CLEARCUT_ACCEPTANCE_ID_TOKEN` only. The first local case binds the verified
`/api/me` actor hash and the six-project mapping; later local cases must match.
National cases can finish before that local setup exists.

Local execution checks current live service/Firebase config, actual saved title,
jurisdiction and exact location pairs (`country_code` in cases becomes `country`
in settings). It requires empty configured local research, calls the real private
`/questions` route, compares the exact deterministic application coverage-gap
response and empty citations, then verifies unchanged tracker/settings/research.
It does not use a keyword score over generated legal advice and performs no
clearance transition or local-research POST.

## Receipts and interpretation

`evaluation.json` always accounts for all twelve cases, including those not run.
The exclusive local lock and atomic/fsynced write precede each external evaluation.
Completed cases are never rerun. Interrupted calls retain `call_outcome_unknown`
and are not automatically retried. Preserve the receipt for reconciliation; do
not erase a result to bypass the unknown outcome. A changed target, case manifest,
source receipt, model or budget rejects resume. Local account/mapping changes also
reject local execution. Identical inputs may resume remaining unverified cases.

Exit 0 means the selected case is structurally verified (or the command only
printed a plan). Exit 2 means setup is missing/invalid; exit 3 means the selected
case is failed, unverified or has an unknown call outcome. Read the structured
result, not just the exit code. No command sends outreach or activates schedules.

The receipt retains bounded generated national answers and official quotation
excerpts for semantic assessment. These are public test questions/source passages,
not screenplays. Tokens, private tracker rows and provider exception bodies are
excluded; tracker readback is represented by a hash. Store receipts privately.

Assess whether the cited article actually supports the claimed principle,
limitations and answer separately against the preserved source. The evaluator
always records `semantic_assessment: unverified` and `legal_clearance: false`;
semantic assessment does not require an approval gate before executing structural
tests. All twelve structural results still do not prove comprehensive jurisdiction
coverage or overall release acceptance.
