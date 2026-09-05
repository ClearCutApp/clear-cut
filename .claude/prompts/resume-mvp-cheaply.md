# Resume the ClearCut MVP without burning the session

Paste this into a fresh session. It carries the state; do not re-derive it.

---

## What happened, and why this prompt exists

On 2026-09-05 a session took ClearCut from "one screen and a flat API" to a
merged `develop` with a domain-partitioned contract, a rescued 1,688 lines, and
a green 7-gate build. It then hit the session limit with two workers mid-flight,
and both died at 429.

The usage breakdown named the cause: **91% subagent-heavy, 70% above 150k
context, 49% from `general-purpose` subagents.** Nine Opus subagents ran in one
session — four of which only read files and reported back.

Read `.claude/AGENT.md` §13 (Subagent economics) before spawning anything.

---

## State as of the cut

Branch `develop`, pushed, **7 gates green**. Read `.claude/CHECKPOINTS.md`
§Active for the board; everything below is what the board does not say.

**Landed and merged into `develop`:**

- `feature/rescue-item-panel`, `feature/rescue-ask-view` — 1,688 lines that
  existed in no commit and no stash, recovered from two abandoned worktrees.
- Git flow established. `feature/api-by-domain` merged; the only conflict was
  the board, four hunks, both sides kept.
- Live gate corrected: it read only pytest's exit code, and pytest exits 0 when
  every test skips, so "nothing was contacted" printed as a pass.
- README, four ADRs (0012-0015), an ADR index, supersession banners on ten
  `docs/resources/` files, and `docs/plan/sdd.md` re-graded.
- `docs/api/openapi.yaml` — the frozen contract, 20 operations, six tags.
- `AnalysisJob` + five new ports.
- W3's web dashboard: Projects, Overview, the item panel, the whole navigation
  drawn with unbacked entries greyed and reasoned. 52 test files, 312 tests.

**Branched, not merged:**

- `feature/data-plane` (W1, 6 commits) — **deliberately red, 5 passed 2 failed.**
  The re-keyed `TrackerStore.latest` now needs `project_id`;
  `adapters/http/routes.py:308,320` does not pass it, and both those routes are
  the top-level tracker paths the contract already moved under their project.
  Also `tests/unit/adapters/test_routes.py` (4 failures, 28 mypy) and a 3-line
  `_FakeVectorStore.get_documents` stub in `tests/unit/test_composition.py`.
  **That red is W2's work, not a defect to triage.**

**Not started:** W2 (HTTP partition, branch from `feature/data-plane`) and W4
(Script Review notepad, branch from `develop` + `feature/rescue-ask-view`).
Both briefs died at 429; both worktrees are dead and should be reaped.

**Live tier, measured through the corrected gate:** 9 passed, 5 skipped, 0
failed in 92 seconds. Every skip is a missing variable, not a broken service.
W1's run against the deployed services was 3 failed / 17 passed / 7 skipped;
those three failures are true — the deployed ClickHouse still carries the old
keys, because `CREATE TABLE IF NOT EXISTS` leaves them alone.

---

## Blocked on a human

1. **`infra/provision_tracker_schema.py --recreate --force`** drops and recreates
   five tables, destroying the demo project's clearance state. It is the only
   way to land the ADR 0014 re-key. **Ask before running it.**
2. **`CLEARCUT_LIVE_SCRIPT_GCS_URI`** — a `gs://` path to a real screenplay PDF.
   Now documented in `.env.example` and `infrastructure.md` §8, still unset.
   Without it Document AI has never parsed a PDF from a cold start.
3. **`GRAFANA_URL` + `GRAFANA_TOKEN`** — a `glsa_` service account with
   `dashboards:write`. The `glc_` OTLP pair authenticates but lists zero stacks.
4. **`NOTIFY_WEBHOOK_URL`** is blank, which skips the end-to-end test.

---

## Do these three things first, before any feature work

They are cheap, and they are why the last session ran out.

### 1. Reap the dead worktrees

```bash
git worktree list                      # three agent-* worktrees remain
git worktree remove .claude/worktrees/agent-<hash>
```

**Check `git status --short` in each first.** Two "stale" worktrees in the last
session held 1,688 uncommitted lines that existed nowhere in git. `remove`
destroys that silently.

### 2. Split the board

`.claude/CHECKPOINTS.md` is **18,486 lines / 1.2 MB**, and roughly three
quarters of it is `## Archive`. It is the most expensive object in this
repository: every agent that greps it pays for all of it, and the docs audit in
the last session read the whole thing.

Move `## Archive` to `.claude/ARCHIVE.md`, leave a one-line pointer, and check
`.claude/init.sh verify` still passes — it parses this file.

Expect the working board to drop under 5,000 lines. That alone is a large share
of the 70%-above-150k number.

### 3. Write the shared worker preamble

Four workers in the last session were each told to read `AGENT.md`,
`WRITING.md`, the contract, and the same four traps. That brief is now
`.claude/prompts/worker-preamble.md` — write it once, then every brief says
"read `.claude/prompts/worker-preamble.md`, then:" and names only what differs.

It must carry the traps that actually cost time:

- `web/src/architecture.test.ts` fails the build on **dead CSS** — write the
  component before its partial.
- `.stylelintrc.json` **bans `100vh`/`100dvh`/`100svh`/`100lvh`**. The mockup's
  locked shell cannot be ported; the page scrolls.
- Only `web/src/api/client.ts` may hold a quoted `/api/` literal.
- `test_no_adapter_module_reads_the_environment_directly` greps adapter files
  for the literal `os.environ` — **a docstring mentioning it fails the test.**
- `test_environment_contract.py` asserts bidirectional equality between
  `_required_env`, `.env.example` and `infrastructure.md` §8. A new required
  variable lands in all three or none. `SCRIPTS_INTAKE_BUCKET` is pending.
- `unittest.mock` is banned (AGENT.md §5). Hand-written fakes, bound by
  annotated assignment.
- Never `Co-Authored-By`. Stage by explicit path, never `git add -A`.

---

## The remaining work

Two workers, run **one at a time**, not in parallel. Parallelism was what made
the last session expensive, and these two lanes are not independent anyway —
W2 must take a red branch green before anything merges.

**W2 — HTTP partition.** Branch from `feature/data-plane` as
`feature/api-partition`. Take it from 5/2 to 7/0. Implement
`docs/api/openapi.yaml` exactly: six domain modules under `adapters/http/`,
`openapi.py` with a `DOMAINS` tuple that raises on duplicates, a two-way drift
test, the eleven new use cases, `domain/highlight.py::spans_for` per ADR 0015,
202-plus-`Location` per ADR 0013, and `SCRIPTS_INTAKE_BUCKET` in all three
places at once. Delete `routes.py`, `docs.py`, `health.py`.

**W4 — Script Review.** Branch from `develop`, merge `feature/rescue-ask-view`.
The notepad: white paper, monospace, numbered lines, gutter status dots, inline
highlights **rendered from the server's `spans` array — do not write a text
matcher** (ADR 0015). Toolbar, word count and zoom are net-new invention; the
design HTML has none of them. The script is read-only server data, so the
toolbar is drawn disabled with a reason rather than wired to nothing.

**Design authority: the screenshots win over
`~/Downloads/gemini-code-1788468625606.html`.** They disagree. The HTML has no
toolbar, no word count, no gutter dots, is not editable, and its right rail is a
single-finding inspector rather than a filterable list. Read it for exact CSS
values only.

---

## How to run this session so it survives

- **One worker at a time.** Merge and verify before launching the next.
- **Model by job, not by habit** — AGENT.md §13. A read-and-report agent is
  `haiku` or `sonnet`. Opus is for the writer holding a design in its head.
- **Never delegate a verification you can run yourself.** `init.sh check` is one
  Bash call; a subagent asked to "check the gates" costs a hundred times that.
- **Trust a worker's report, then verify with one command, not one agent.**
- **`/compact` when a lane closes**, not when the context bar goes red.
- Do the cheap high-value work inline: doc fixes, single-file edits, git
  hygiene, running gates. The last session's README fix, ADRs and env-contract
  guard were all inline and cost almost nothing next to one worker.

---

## The rule this project keeps re-learning

Three separate times, this codebase reported success it had not earned: a live
gate that printed `1 passed` having contacted nothing; an SDD grading the same
check DONE and MISSING in four places; a README whose only two commands 404'd.
Each survived because **the check did not look where the evidence lived.**

Before writing a status anywhere, run the thing. Then write what it printed.
