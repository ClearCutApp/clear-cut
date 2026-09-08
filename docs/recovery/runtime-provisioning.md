# Recovery runtime provisioning

The repository now includes inspectable, repeatable provisioning tools for the
five packaged Cloud Run Jobs, their scoped execution permissions, eight Firestore
queue indexes and four recurring schedules. This checkpoint made **no cloud
changes**. The example manifest contains placeholders and is not deployable.

## Prepare the exact release configuration

Copy `runtime-manifest.example.json` to an operator-owned file and replace every
placeholder. Supply the exact built image digest, existing project/region, existing
service accounts, public provider configuration and numeric Secret Manager version
references. Secret values never belong in this manifest, generated environment
files, command output or Git. Mutable image tags and `latest` secret versions are
rejected. `CLICKHOUSE_HOST`, `CLICKHOUSE_USER` and `OTEL_EXPORTER_OTLP_ENDPOINT`
may each be supplied either in `environment` or as a numeric-version reference in
`secret_versions`, never both. Host and user are required in one location; the
telemetry endpoint remains optional. Preserve existing Secret Manager bindings
instead of reading secret values into the plan. The example uses secret references.
Only worker/activity jobs receive ClickHouse host/user references; only the worker
receives the telemetry endpoint. Other dispatcher secret scopes stay unchanged.
Use a dedicated job prefix; existing jobs without the recovery ownership
label will not be overwritten.

The chosen region must agree with the existing data plane (`us-central1` for the
current Firestore database and Cloud Run deployment). Cloud Run, Firestore, Cloud
Scheduler and the required provider APIs must be enabled. Operator credentials need
permission to configure these resources and act as the named service accounts.
The tools do not create accounts or grant project-wide administrator roles.

Runtime data access remains an explicit provisioning prerequisite:

| Identity | Required data/service access |
| --- | --- |
| Worker | Firestore operational state; private intake/artifact bucket; Document AI, Vertex AI and grounded search; the relevant BigQuery lore reads; its selected provider secrets |
| Analysis dispatcher | Firestore jobs; execute/cancel the named worker with argument overrides |
| Activity dispatcher | Firestore outbox; named ClickHouse credentials and the additive analytics table |
| Lore dispatcher | Firestore lore queue; private artifact bucket; Vertex embeddings; regional BigQuery jobs and scene-vector table writes |
| Notification dispatcher | Firestore notification queue/bindings; only the configured destination secret |
| Scheduler | Execute only the four dispatcher Jobs |

Restrict GCS permissions to the existing private bucket, BigQuery data permissions
to the intended dataset/tables, secret access to the referenced secrets, and
execution roles to each specific Job. Preserve the existing API service's
independent identity. The tool verifies execution bindings, not all data-plane
IAM. Provision and read back the additive ClickHouse and BigQuery schemas with
their dedicated tools before activation. No legacy table is recreated.

Generate a plan locally:

```sh
.venv/bin/python -m infra.provision_runtime_jobs --manifest OPERATOR_MANIFEST.json --output /tmp/clearcut-runtime-plan
.venv/bin/python -m infra.provision_runtime_indexes --project PROJECT_ID
```

The first command writes public environment JSON files and a plan containing
argument arrays for deployments, IAM and schedule activation. Neither default
command contacts Google Cloud. Worker configuration replaces the image's
Gunicorn command with `python -m clearcut.worker`; its required analysis argument
is supplied only by the persisted dispatcher request. Platform retries are zero;
application leases and checkpoints own recovery. Jobs have one task and one
parallel slot. Actual overlapping executions remain protected by fenced leases.

## Add indexes and configure jobs

After inspecting the plan, the following are explicit cloud mutations:

```sh
.venv/bin/python -m infra.provision_runtime_indexes --project PROJECT_ID --apply --receipt /tmp/clearcut-index-submissions.json
.venv/bin/python -m infra.provision_runtime_indexes --project PROJECT_ID --verify
.venv/bin/python -m infra.provision_runtime_jobs --manifest OPERATOR_MANIFEST.json --output /tmp/clearcut-runtime-plan --apply-jobs
```

Indexes are compared by collection, query scope and ordered fields. Existing
READY or CREATING indexes are retained. Submission is recorded durably before
create; an unknown response is not blindly retried. Keep the receipt until all
eight indexes read back READY. An unresolved receipt needs authoritative operation
inspection; deleting the receipt is not recovery. The tools never delete indexes.

Job configuration waits for index readiness, then reads each dedicated resource.
Matching configurations are not redeployed. New or changed owned jobs are read
back against image, command, arguments, service account, public environment,
secret references, resource limits, retries and task count. It then adds only
job-scoped `roles/run.jobsExecutorWithOverrides` for the analysis dispatcher and
`roles/run.jobsExecutor` for Scheduler. `CONFIGURATION_VERIFIED` is control-plane
configuration evidence, **not** proof that the worker successfully ran.

## Explicit scheduling activation

Do not activate while Firebase authentication, schemas, data IAM, project migration
or release verification are unresolved. Creating a Cloud Scheduler job enables
recurring requests; it is therefore separate from Job configuration. Once the
release configuration is ready, this explicit operation starts provider work:

```sh
.venv/bin/python -m infra.provision_runtime_jobs --manifest OPERATOR_MANIFEST.json --output /tmp/clearcut-runtime-plan --activate-schedules
```

Activation rechecks all Job configurations, index readiness and scoped execution
permissions. It creates or updates four one-minute schedules, and explicitly
resumes owned paused schedules when this activation command is chosen. Identical
enabled schedules are unchanged. Unowned schedules are never replaced. Requests
use OAuth for the Google API endpoint, JSON `{}` bodies and a 30-second attempt
deadline. Scheduler retries are zero; the next scheduled delivery and application
leases recover lost acknowledgements. The worker Job itself is never scheduled
or run directly by these tools.

Read back schedules and then prove actual authenticated user journeys, provider
receipts, queue progress, cancellation, worker termination/recovery and projection
freshness. An accepted-but-unknown operation remains unverified. For rollback,
pause the four owned schedules before restoring a previously verified image
manifest; already running executions may continue and require explicit inspection.
Do not remove transactional data, erase outboxes or assign legacy ownership.

## Evidence and command references

Offline tests cover the complete plan, secret/reference validation, project scope,
unknown index submission recovery, idempotent resource inspection, ownership
protection, configuration readback, activation prerequisites and explicit resume.
Real provisioning and invocation have not been performed. Commands follow the
current official [Cloud Run Job deploy reference](https://docs.cloud.google.com/sdk/gcloud/reference/run/jobs/deploy),
[Scheduler HTTP reference](https://docs.cloud.google.com/sdk/gcloud/reference/scheduler/jobs/create/http),
[Firestore composite-index reference](https://docs.cloud.google.com/sdk/gcloud/reference/firestore/indexes/composite/create)
and [Cloud Run IAM role definitions](https://docs.cloud.google.com/iam/docs/roles-permissions/run).
