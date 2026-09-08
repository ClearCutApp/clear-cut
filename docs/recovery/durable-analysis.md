# Durable revision analysis — September 6, 2026

Live analysis accepts `POST /api/projects/{project_id}/scripts` with
`revision_id` and `jurisdiction_code`. The server verifies the saved revision,
active workspace membership and explicit project grant, then commits the full
request and launch intent before returning 202. Browser storage URIs and file IDs
do not start live analysis. The mock upload journey remains a disclosed fixture.

Poll the returned `Location`; `/analyses/current` recovers the active job after a
reload. `POST /analyses/{analysis_id}/cancellation` prevents further checkpoint
publication and result publication. An already submitted Parallel task can keep
running remotely; ClearCut does not claim remote cancellation or a refund.

## Runtime configuration

The existing image includes both entrypoints under the installed package:

- Worker: `python -m clearcut.worker --analysis-id <persisted-id>`.
- Scheduled dispatcher: `python -m clearcut.dispatcher`.

Configure the worker Cloud Run Job with **command `python`**, one task,
zero platform retries, and the existing live provider configuration and secret
references. The dispatcher supplies the entire argument array
`["-m", "clearcut.worker", "--analysis-id", "<id>"]`; it never waits for execution
completion on a launch request. Do not leave the image's Gunicorn command active
for either job. The dispatcher image command is `python`, with arguments
`-m,clearcut.dispatcher`.

The dispatcher requires `GOOGLE_CLOUD_PROJECT`, `CLEARCUT_ANALYSIS_JOB` (bare job
name), and optional `CLOUD_RUN_REGION` (default `us-central1`). Schedule it at least
once per minute using an authenticated Cloud Scheduler invocation of the
dispatcher job. Its service account needs Firestore access plus
`roles/run.jobsExecutorWithOverrides` scoped to the worker job. The scheduler
identity needs permission to execute only the dispatcher. Worker credentials
need the existing scoped provider, private GCS and Firestore permissions.

Provision composite collection indexes for `analysis_jobs`:

- `state ASC, available_at ASC` (queued retry dispatch).
- `state ASC, lease_until ASC` (expired running execution recovery).

Do not deploy this HTTP change without the worker, scheduler, indexes and runtime
IAM. None of those new Cloud Run resources or permissions has been provisioned or
live-verified in this checkpoint. Firebase terms/app configuration, backups,
migration ownership and release verification remain independent blockers.

## Publication and retries

Workers claim a 90-second fenced lease and renew it every 20 seconds. A failed
renewal stops new stage work; every checkpoint and final publication checks the
persisted fence, lease and cancellation. Retry backoff is persisted (15, 30, 60
seconds), with four total attempts. A dispatcher launch response can be lost;
duplicate workers cannot claim the same live lease or publish a duplicate result.

Provider results and exact revision PDF scene/block anchors are immutable GCS
artifacts. Parallel creation intent is saved before submission, then the returned
run ID is saved. Known run IDs resume polling. An accepted-but-unrecorded creation
outcome becomes an explicit research gap, never an automatic second paid task.

All clearance items, including removed assets, are staged in a new generation.
Batches cap both write count and estimated bytes; oversized individual records
fail explicitly. Staged generations remain invisible. A constant-size Firestore
transaction checks the human-edit epoch and worker fence, then publishes the
generation pointer, script manifest index, terminal job and one outbox event.
Human changes during staging cause a rebase using retained provider outputs.
Human notes, evidence, assignment, deadlines and request drafts are retained.
Changed scene content or production context requires review; unchanged stable
scene IDs can move without invalidating their applicable clearance.

ClickHouse analytics/history and BigQuery lore projection dispatch are implemented
and offline verified. Their deployed delivery is not represented as completed.
See runtime-provisioning.md for additive index/Jobs/IAM/Scheduler tooling. New
script/finding reads use the committed manifest immediately.
Legacy analysis polling remains available; legacy records are not automatically
assigned, migrated, resumed or exposed.

## Verification evidence and limits

Offline tests cover request/launch atomicity, duplicate claims, expired fences,
checkpoint retention, cancellation, bounded retries, 701-item generations with
maximum Unicode details, incomplete publication, human-edit races, exact replay,
immutable overlays, revision applicability and unknown Parallel create outcomes.
The independent verifier reran 18 selected cases successfully. These exercise SDK
transaction callbacks against deterministic fakes, not a Firestore emulator or a
live concurrent database. Actual process kill/restart, Cloud Run launch, scheduled
recovery and deployed browser authentication remain unverified.
