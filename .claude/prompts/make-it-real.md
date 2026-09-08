> **Historical workflow — superseded September 7, 2026.** This document is retained
> as history. Its checkpoint, agent-loop, runtime tool/model and approval instructions
> do not govern current recovery work. Follow [AGENTS.md](../../AGENTS.md), the
> [approved specification](../../docs/recovery/specification.md) and [current situation](../../docs/recovery/situation-2026-09-07.md). Use one writer,
> the active runtime permissions and ordinary repository checks; do not revive a
> historical loop or mark deployment complete from checkpoint status.

# Implement and review the features. Make it real, not mocks.

Paste this into a fresh session.

---

## The instruction

Implement the remaining ClearCut features and review what already exists. Every
claim you make about a feature working must be backed by evidence you produced
in that session: a gate result you ran, a request you sent, a screen you opened.
Not a test name. Not a file that exists. Not a subagent's report you did not
check.

**Nothing counts as done until it runs against real services.** `CLEARCUT_MODE=mock`
is for a suite, not for a demo and not for a status report.

---

## Why this looked stuck, precisely

Read this before diagnosing it yourself, because the answer is not what it
looks like and the wrong diagnosis costs a day.

The work was not stuck. **The work was undeployed.**

On 2026-09-05 the codebase went from a flat five-route API and one real screen
to: six tagged API domains, analysis as a job resource, durable findings,
server-computed highlight spans, four screens, a browser upload, and a
destructive migration that removed a silent data-loss defect. Fifty commits.
Seven gates green throughout.

And the Cloud Run URL served **none of it**, because the last deploy was
2026-09-04 01:20 UTC. Every screenshot taken to demonstrate progress was
`localhost` in mock mode. From outside, across two days of real work, the
product did not change once. That reads exactly like a stuck project, and
anyone looking at the live URL was right to say so.

Two failures produced that, and both are process, not code:

1. **Work was reported from the branch, not from the deployment.** A merge to
   `develop` with green gates was treated as delivery. It is not. Nothing is
   delivered until it is serving.
2. **Every demonstration ran in mock mode** because mock needs no credentials
   and starts in five seconds. It is the fastest way to show a screen and the
   slowest way to learn the truth: the mock adapters cannot fail the way the
   real ones do, so a screen that works in mock proves nothing about the
   product.

The deploy that closed this took **one command and found two real defects in
four minutes** — a missing required variable that stopped the container booting,
and a documentation row naming a bucket that does not exist. Both had been sitting
in the repo, both were invisible to 794 passing tests, and both would have been
found on day one by deploying on day one.

---

## The rule that follows from it

**Deploy after every merge to `develop`.** Not at the end. A revision that
serves is the only status report that cannot be wrong.

```bash
gcloud run deploy clearcut --source . --region us-central1 \
  --min-instances 1 --no-cpu-throttling --allow-unauthenticated
```

`--min-instances 1` and `--no-cpu-throttling` are not optional. ADR 0013 runs
the analysis on a background thread in the same process; on Cloud Run's defaults
the CPU is throttled to near-zero between requests and the instance is reclaimed
when idle, so the job freezes the moment the 202 returns and the producer polls a
row that says `RUNNING` until the reaper marks it `FAILED`.

Then prove it, against the URL and not against localhost:

```bash
U=https://clearcut-813918777633.us-central1.run.app
curl -s "$U/api/health"                 # must say {"mode":"live"}
curl -s "$U/api/openapi.json" | jq '.tags[].name'
curl -s -X POST "$U/api/projects" -H 'Content-Type: application/json' \
  -d '{"title":"...","jurisdiction_code":"AR"}'
curl -s "$U/api/projects"               # read it back out of real ClickHouse
```

If `mode` says `mock`, the deployment is misconfigured and every screenshot
taken from it is worthless.

---

## State as of 2026-09-06

**Live and verified**, revision `clearcut-00007-7np`, `{"mode":"live"}`, 17
paths, six tags. A project created through the live API persists in ClickHouse
Cloud and reads back. The migration is applied: `tracker_items` is
`ORDER BY (project_id, item_id)` and `script_versions` is
`ORDER BY (project_id, script_id)`, confirmed against `system.tables`. Two
projects can no longer merge into one row.

**Live tier: 19 passed, 1 failed, 7 skipped.** The failure is the Parallel Task
API returning a connection error, which does not reproduce. Every skip is a
missing variable, not a broken service.

**Still needed from a human:**

- `CLEARCUT_LIVE_SCRIPT_GCS_URI` — a `gs://` path to a real screenplay PDF.
  Cheapest and highest value: Document AI has never parsed a PDF from a cold
  start, so delivery phase 1 cannot be honestly marked met.
- `GRAFANA_URL` and `GRAFANA_TOKEN` — a `glsa_` service account with
  `dashboards:write`. The `glc_` OTLP pair authenticates and lists zero stacks.
- `NOTIFY_WEBHOOK_URL` — blank, which skips the end-to-end test.
- `SCRIPTS_INTAKE_BUCKET=clearcut-scripts-intake` is set on Cloud Run but is
  **not in the local `.env`**, so a local live run still fails on it.

---

## What to build, in order

1. **An end-to-end run against live services.** Upload a real screenplay
   through the browser, queue the analysis, watch the job reach `SUCCEEDED`,
   open Script Review, see real findings marked on real text. This takes twelve
   to twenty minutes of wall clock and is the single most valuable thing left.
   It has never been done through the UI.
2. **Reconcile `.claude/CHECKPOINTS.md`.** It says 19 TODO. Most of CP-063
   through CP-076 are built and merged. A session dispatching from that board
   will re-implement work that exists.
3. **Authentication.** There is none — zero hits for `login|session|auth|tenant`
   across the HTTP layer. Every route is open and `project_id` is a guessable
   string. Never planned, never boarded, never costed. Acceptable for a demo,
   disqualifying for a second customer.
4. **The delta path against live.** `EvaluateDelta` has only ever run in mock.
   Uploading v2 with one changed scene is the feature that makes re-clearing a
   rewrite cheap, and it is unproven.
5. **Clearances, Documents, Reports.** Greyed in the sidebar with honest reasons
   because no resource backs them.

---

## How to review

Review is not a second opinion on a diff. Run the thing.

- `./.claude/init.sh check` — seven gates. One Bash call. **Never delegate this
  to a subagent** (`AGENT.md` section 13).
- `./.claude/init.sh live` — needs `.env`. It reports how many tests actually
  ran; an all-skipped run is named as a configuration gap rather than a pass,
  because for two days it was not.
- Open the screen in a browser. Three defects this month were invisible to a
  green suite and obvious on the page: raw JSON rendered as an error message, a
  Script Review showing zero findings because a version tie sorted the wrong way,
  and a whole deployment two days stale.

---

## On speed

The slow part of 2026-09-05 was not implementation. It was nine Opus subagents
in one session — four of which only read files and reported back — which
exhausted the session limit and killed two workers mid-flight.

Read `AGENT.md` section 13 before spawning anything. Read files with `haiku`.
Map and audit with `sonnet`. Run a gate inline, never as an agent. One writer at
a time unless the file sets are provably disjoint. And put the shared half of
every brief in `.claude/prompts/worker-preamble.md` instead of repeating it four
times.

---

## The standard

This repository has three recorded cases of a status that was never earned: a
live gate that printed `1 passed` having contacted nothing, a design document
grading the same check DONE and MISSING in four places, and a README whose only
two commands returned 404.

Each survived because the check did not look where the evidence lived.

Before writing a status anywhere — a commit message, a board entry, a reply —
run the thing, then write what it printed.
