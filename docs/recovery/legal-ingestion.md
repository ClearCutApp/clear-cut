# Official-source ingestion

The dated source manifest contains 19 reviewed national texts across six launch
countries. The CLI is implemented and tested offline; these texts have **not**
been imported or evaluated by this checkpoint. Source discovery is not proof of
current legal completeness, permission, or provider grounding.

Print the exact plan without credentials or network access:

```sh
.venv/bin/python infra/ingest_legal_corpus.py
```

After inspecting the target data store, bucket permissions and schema, execute
against the existing resources using a fresh local evidence directory:

```sh
.venv/bin/python infra/ingest_legal_corpus.py --apply \
  --project clearcut-hack --bucket clearcut-legal-corpus \
  --datastore clearcut-legal-corpus --location global \
  --state-dir /private/tmp/clearcut-legal-ingestion-2026-09-06
```

This uploads official public texts and starts a Discovery Engine import. It does
not provision resources, delete earlier documents, send messages, or modify
clearance decisions. Run only after the concrete cloud action is authorized.
The bucket must be readable by the configured Discovery Engine service identity.
The `jurisdiction` string property must be indexable; retain existing schema
properties when changing it. Google's [schemas.patch API](https://docs.cloud.google.com/generative-ai-app-builder/docs/reference/rest/v1/projects.locations.collections.dataStores.schemas/patch)
supports this change; the historical console-only guidance is superseded.

Each source is downloaded over bounded HTTPS with official-host validation on
every redirect. Original bytes and extracted UTF-8 text are stored under immutable
hash paths. PDF page exclusions and parser versions are recorded. Colombia's
Decision 485 page is excluded; Mexico's replacement privacy law must contain its
2025 publication marker. HTML encoding and text extraction failures become gaps,
not empty imported documents. Long official texts may still need source-specific
review; the CLI never equates a successful parser with legal completeness.

`receipt.json` binds the exact manifest and target. Re-running the same command
reuses verified local bytes and an existing import operation. A changed manifest
requires a new evidence directory. The CLI writes the submission intent before
calling the provider: if the response is lost before its operation ID is saved,
it stops with `submission_unknown`. Inspect provider operations and reconcile the
actual identity before another submission; do not delete the receipt to retry.

Imports use stable document IDs and incremental reconciliation. A successful
operation must have no reported failures, and every document must read back with
the exact content URI and provenance hashes. The CLI waits at most 45 seconds per
invocation by default; an unfinished operation remains `importing` and exits
nonzero. Re-run to poll again. `imported_readback_verified` means import/readback
only: search indexing and model grounding still require the dated evaluation
cases. Official [import documentation](https://docs.cloud.google.com/generative-ai-app-builder/docs/reference/rest/v1/projects.locations.collections.dataStores.branches.documents/import)
defines the incremental request and asynchronous operation.

National tests require a supporting passage, correct article and limitation;
matching URLs alone do not pass. The six local cases deliberately supply no
project research and must return an explicit gap without guessed permits, fees,
or authorities. Persist actual answers, cited passages, source hashes, date and
human evaluation separately. All 12 cases currently remain unverified.

The US current trademark source was inaccessible during discovery. Its 2024
historical fallback is excluded from active ingestion. Congress commentary and
Canada's privacy overview are also excluded from normative ingestion. Existing
legacy corpus documents are not deleted automatically; inventory and quarantine
any superseded or unproven entries before claiming the active corpus is clean.
US state, Canadian provincial, and all location-specific requirements remain
explicit coverage gaps.

`fetch_legal_corpus.py` is candidate discovery only. The old retrieval-plane
provisioner discards import operation results and must not be used as release
verification. This receipt-based ingestion path supersedes its import stage.
