# Authenticated deployed acceptance

`python -m infra.deployed_acceptance` exercises the current deployed HTTP contract
using a generated synthetic screenplay. It replaces the obsolete synchronous,
unauthenticated end-to-end test. Unit tests establish harness behavior only.

Set `CLEARCUT_ACCEPTANCE_ID_TOKEN` in the environment to a current Firebase ID
token for a verified test account. Never put the token in command arguments,
receipts, screenshots or documentation. Refreshing the token for the same account
is supported. The account must be authorized to create a workspace.

Run read-only preflight first (substitute the deployed HTTPS origin):

```sh
.venv/bin/python -m infra.deployed_acceptance \
  --target https://DEPLOYED_ORIGIN --run-id acceptance-20260907 \
  --directory /tmp/clearcut-acceptance-20260907
```

Preflight checks live mode, Firebase client configuration, current OpenAPI paths,
asynchronous analysis, anonymous project denial and authenticated identity. An old
deployment fails before any writes. It creates a local private receipt only.

After authorizing synthetic cloud writes and provider execution, add `--advance`.
Each invocation advances at most eight stages by default (`--steps 1..32`). A
running analysis causes an immediate `pending` return after one poll; invoke the
same command later. There is no busy polling or provider retry loop. Individual
HTTP requests use a 10-second connect/45-second timeout and a 16 MiB response cap.

The flow creates an owned, visibly synthetic workspace/project; imports a generated
PDF; edits the imported draft; verifies stale-write 409 and unchanged readback;
freezes and reads the revision; queues revision analysis with 202; polls its fixed
identity; reads the committed result; uploads and downloads synthetic evidence;
records and reconfirms one synthetic clearance; captures the current report
selection; creates an immutable report; verifies PDF/CSV contents. Synthetic
clearance does not authorize any real-world use. Do not run against user projects.

The receipt binds the HTTPS origin, verified actor hash, fixture hash, run marker,
Firebase project and OpenAPI hash. It records resource IDs, versions, response
statuses and content hashes, never tokens, response bodies or screenplay text.
An exclusive local lock prevents concurrent writers. Every mutation has an atomic,
fsynced intent before dispatch. Preserve the directory across restarts.

| Status / exit | Meaning and continuation |
| --- | --- |
| `ready` / 0 | Preflight passed; no remote writes performed by this invocation. |
| `missing_setup` / 2 | Missing token, inaccessible preflight, lock or receipt mismatch. Correct setup; preserve existing receipt. |
| `pending` / 3 | Step budget exhausted, safe read temporarily unavailable, or fixed analysis still running. Resume the same run. |
| `unknown` / 4 | Mutation may have committed, including an interrupted import that stored an original. Stop and reconcile the exact intent/resources with service state. No automatic retry or reset exists. |
| `failed` / 5 | Readback or terminal analysis check failed. Preserve evidence and diagnose before a new run. |
| `success` / 0 | All stages completed for this synthetic HTTP journey; not release acceptance for every integration. |

Do not delete a receipt or choose a new run ID to bypass an uncertain mutation.
Resource creation is not idempotent at these HTTP endpoints. There is no automatic
cleanup: use the receipt resource ledger for a separately authorized cleanup, and
retain analysis/report evidence. Never manually erase `intent` to force a retry.

The live pytest entry requires the same token and
`CLEARCUT_ACCEPTANCE_TARGET`, `CLEARCUT_ACCEPTANCE_RUN_ID`,
`CLEARCUT_ACCEPTANCE_DIRECTORY`, `CLEARCUT_ACCEPTANCE_ADVANCE=yes`. It performs one
bounded invocation and asserts `success`; pending is a failure with a resumable
receipt, not a passing skipped provider call.

The success result is scoped to this one HTTP journey and stored receipt, not a
fresh rerun of previously completed steps. Original same-name upload preservation,
private cache headers and citation content quality require separate checks.

Separate deployed evidence is still required for browser sign-in/verification and
refresh, a second user's isolation, worker process restart and lease recovery,
cancellation/retry, voice, national/local grounded research, analytics and telemetry
delivery, notifications, schedules, migration and rollback. This harness neither
activates schedules nor proves all integrations or release readiness.
