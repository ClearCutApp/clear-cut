# Private project notifications

Status: implemented and verified offline; no destination is configured or sent by this recovery work. Cloud Run scheduling, Firestore indexes, runtime IAM and a real receiver receipt remain unverified.

A producer's Notify action creates a private, immutable attention record without changing the clearance version or status. It rechecks the active project grant, organization membership and effective clearance version in a Firestore transaction. Reasons are limited to 2,000 characters. Authorized project readers can browse 50 records per page and keep their own read marks. The UI preserves reason text when recording fails.

The live legacy global webhook adapter is disabled. An unbound project records in-app only. Organization membership or a globally configured `NOTIFY_WEBHOOK_URL` does not authorize external delivery from any project.

## Explicit destination binding

Only deployment operators configure `notification_bindings/{binding_id}` and the private project's `notification_binding_id`. A binding contains an organization, an explicit list of private projects, a positive version, enabled state, endpoint environment-variable name, and SHA-256 of the exact intended HTTPS URL. The endpoint itself stays in deployment secrets. Queue intents capture a fingerprint of all these binding fields. A disabled, removed, reassigned or changed binding blocks existing intents rather than rerouting them. Rotating the URL requires a new version and matching hash; old queued intents remain blocked.

Use an explicitly identified workspace and project list; never infer a legacy owner. With the intended endpoint already set in the named environment variable, inspect the additive plan:

```sh
.venv/bin/python -m infra.provision_notification_binding --project clearcut-hack --organization IDENTIFIED_ORG --private-project EXPLICIT_PROJECT --binding-id production-alerts --version 1 --endpoint-env NOTIFY_WEBHOOK_URL
```

`--apply` writes the inspected binding and project pointers transactionally after checking every project's organization and existing destination. It never prints the URL. New bindings start at version one; changes require the next version. `--disabled` creates a versioned disabled binding. Receiver URLs are operator-controlled, HTTPS only, and redirects are not followed. Browser-managed destination URLs are outside this release.

## Delivery and verification

Run the packaged worker with `python -m clearcut.notification_dispatcher`; `--help` is safe and constructs no cloud clients. Configure `GOOGLE_CLOUD_PROJECT` and the binding's endpoint secret in this Job. Grant only its required Firestore access and secret access. Provision a scheduled invocation and composite indexes for `notification_outbox` on `(state, available_at)` and `(state, lease_until)`, plus the project notifications query on descending creation time and document identity. These deployment changes have not been executed here.

Each invocation considers at most 20 pending or expired deliveries. A 90-second fenced lease covers one 20-second HTTP request, without SDK retries. Failed or unknown responses retry later with exponential backoff, up to five attempts. A receiver-accepted event whose acknowledgement is lost can be delivered again: receivers must deduplicate the stable `event_id` or `X-ClearCut-Event-ID`. There is no exactly-once network guarantee. Revocation is checked when claiming; an already in-flight authorized request cannot be recalled.

External JSON contains only `event_id`, `organization_id`, `project_id`, `item_id`, and the fixed `manual_attention` reason code. It excludes the user's reason, screenplay, contact, note, evidence, attachments and credentials. In-app state distinguishes queued, delivered, blocked and unconfirmed; delivery never confirms legal clearance. No legal outreach or mailbox sending occurs.

Offline tests cover cross-organization and private-project binding denial, reason bounds, stale clearance conflict, private read marks, destination rotation, no global fallback, sanitized payloads, no redirects, lease takeover, accepted-but-unacknowledged retry identity, bounded attempts and provisioning rollback on mismatched project scope. A real receiver and deployed worker remain separate release evidence.
