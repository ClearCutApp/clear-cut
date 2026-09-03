# ADR 0011: The submission runs live on the analyze path

Status: Accepted
Date: 2026-09-03

## Context

The SDD now grades itself. One section is DONE, every port is WIP, three
endpoints and all four verification checks are MISSING, and no phase has met
its own exit criterion. The cause is single and known: `clearcut-hack` does not
exist, so nothing has ever called a provider.

Four days remain. `infrastructure.md` section 11 requires "runtime proof that
calls are real and not mocked" in the submission, and ADR 0003 entered the
Parallel partner track. Mock mode satisfies neither. It was the right hedge
under D36 and it is now labelled honestly in the UI, but a submission resting
on it fails a stated requirement.

Everything cannot ship. Something has to be ruled out on purpose rather than
run out of time, and the ruling belongs in writing before the work starts.

## Decision

Provision every service and run the analyze path live for the submission.
Rank the rest against one test: does it change what a judge sees, or what the
submission truthfully claims?

**Provision all of it.** `infra/provision_data_plane.sh`,
`infra/provision_retrieval_plane.sh` and `infra/provision_tracker_schema.py`
already exist, are unit-tested, and support `--dry-run`. ClickHouse Cloud and
Grafana Cloud are created by hand. This is an afternoon, and skipping it makes
every other decision moot.

**Live for the submission:** Document AI, the Gemini extractor, Vertex AI
Search, BigQuery, ClickHouse, and Parallel. Parallel is not negotiable under
ADR 0003.

**Seed bible facts through infrastructure, not a new endpoint.** The CONTINUITY
finding in section 8(d) needs facts in the LoreStore, and
`POST /api/projects/{id}/bible` is a route plus a use case plus tests. An infra
script calling `BigQueryLoreStore.index()` reaches the same state in an hour.
The endpoint stays MISSING and the SDD keeps saying so.

**Cut for the submission:** `POST /api/projects` and
`GET /api/scripts/{script_id}`. Project ids are strings the analyze request
already carries, and the analyze response already carries the ScriptView
payload, which is why the SPA renders without either.

**Fix the unguarded SDK calls; defer the other three defects.**
`VertexSearchGrounding`, `GeminiSceneExtractor` and `GeminiContinuityCheck`
call their SDKs bare, so a Vertex 503 or a malformed model response reaches the
producer as a 500 reading "internal error". That is the defect most likely to
appear on camera, and live traffic is what makes it likely. `ContinuityCheck`'s
missing instrumentation, `EvaluateDelta`'s untested failure paths, and
`Notifier`'s missing live test wait until after the submission.

**Mock mode stays.** If provisioning fails, `CLEARCUT_MODE=mock` still runs the
demo and the banner still says the data is a fixed sample.

## Consequences

The submission can claim its calls are real, because a live test will have
failed if they were not. Section 8(d) becomes runnable, and phases 1 through 4
can meet their own exit criteria for the first time.

Three of the eight endpoints stay unbuilt, and the SDD reports them as MISSING
rather than quietly dropping them. Anyone reading it after the deadline sees
what was cut and why.

Bible ingestion has no user-facing path. Seeding is an operator action, so a
producer cannot upload a bible in the demo; the facts are already there. That
is a visible product gap and it is the right trade at four days.

Three adapters get error handling under time pressure, which is where mistakes
happen. Each fix ships with a test that fails without it, and the live tier
covers the paths that matter.

Spending the provisioning budget commits real money against the billing
account. Cloud Run at `--min-instances 0` and a free-tier ClickHouse and
Grafana keep it small, but it is no longer zero.
