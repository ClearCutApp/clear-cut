# Identity and durable workspace provisioning

The recovery coordinator enabled Firebase, Identity Toolkit, Firestore and Speech
APIs in the existing project on September 6, 2026. The `(default)` Firestore database
is native STANDARD in `us-central1`, with deletion protection. Point-in-time recovery
and scheduled backups remain pending. No legacy data has been assigned or migrated.

For another environment, inspect the existing database location first. Then use:

```sh
gcloud services enable firebase.googleapis.com identitytoolkit.googleapis.com firestore.googleapis.com speech.googleapis.com --project PROJECT_ID
gcloud firestore databases describe --database='(default)' --project PROJECT_ID
```

Create a missing database only after confirming the intended region matches the
Cloud Run data plane. Do not recreate or relocate an existing database. Enable
backups/PITR and rehearse restore before migration. Add the GCP project to Firebase,
create the ClearCut web app, enable Google and email/password providers, configure
support email and authorized domains, and verify real email delivery.

The server serves public Firebase web-app configuration through `/api/client-config`
using `FIREBASE_WEB_API_KEY`, `FIREBASE_WEB_AUTH_DOMAIN`, `FIREBASE_WEB_APP_ID` and
`GOOGLE_CLOUD_PROJECT`. This supports one image across environments without rebuilding.
The optional local/build override consumes:
`VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`,
`VITE_FIREBASE_APP_ID`. These are public client identifiers, never service-account
credentials. Server identity verification uses the same project ID and runtime ADC.
Grant runtime Firestore/IAM access only to the service account that needs it;
Firebase browser clients must not read Firestore directly. Deny direct client writes.

Use disposable verified test accounts and two new workspaces for acceptance. Check
that membership alone reveals no project, removing membership immediately denies
access, arbitrary file URIs fail, and another project's file ID returns 404. Verify
live Firestore transaction commits and the Firebase token's audience, expiration,
revocation and email verification checks. Do not treat emulator proof as live proof.

Migration requires an explicitly identified legacy owner workspace, preserved IDs,
backups, resumable checkpoints, row/document/object reconciliation and a rehearsed
rollback. Do not infer ownership from existing records or an administrator's email.

Transactional drafts, tracker generations, durable jobs, ClickHouse activity and
BigQuery scene projection are implemented and offline verified. Runtime migration
and live verification remain unfinished. See runtime-provisioning.md for the
inspectable additive index/Jobs/scoped-IAM/Scheduler tooling; no new recovery Job
or schedule has been deployed by this work.
