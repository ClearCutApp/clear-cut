# TOPOLOGY.md — Why this work is not running through the loop

Written 2026-09-05, at the user's request, by the worker on
`feature/script-review`. It answers one question: the repository defines a
`leader` / `implementer` / `reviewer` loop in `AGENT.md` §6, so why is the
current work being done by briefed parallel workers instead, and is that
better.

This is a record for review, not a change to `AGENT.md`. The loop is still
the contract. If the trade-off below is accepted, `AGENT.md` §6 should say
when each topology applies; if it is rejected, the work should move back
onto the board.

---

## 1. What the two topologies are

**The loop** (`AGENT.md` §6, `.claude/agents/*.md`). Three roles share one
state file. `leader` writes checkpoints into `CHECKPOINTS.md`. `implementer`
takes exactly one `TODO`, implements it test-first, sets it `IN_REVIEW`.
`reviewer` reads that one diff, runs the gates, returns `PASS` or
`CHANGES_REQUESTED`. `Attempts` caps at 3, `BLOCKED` is terminal, and
`./.claude/init.sh verify` proves mechanically that the status machine has no
unbounded cycle. Everything is serial: one checkpoint in flight, one writer,
one reviewer, one file of shared state.

**Briefed parallel workers** (what produced `feature/script-review`,
`feature/web-dashboard`, `feature/api-partition`, `feature/data-plane`). A
conductor writes one brief per lane, names each lane's exact file set,
branches each lane off `develop`, and lets the lanes run at the same time.
The shared half of every brief lives once in
`.claude/prompts/worker-preamble.md`. There is no board, no status field, and
no separate reviewer agent — each worker runs `./.claude/init.sh check` itself
and reports the numbers it printed.

---

## 2. Why the loop is not being used for this work

Four reasons, in the order they bite.

**The board does not describe this work.** `CHECKPOINTS.md` currently holds 24
checkpoints: 19 `TODO`, 2 `IN_REVIEW`, 2 `DONE`, 1 `BLOCKED`. None of them
says "build the script review notepad". The screens being built now come from
screenshots the user supplied on 2026-09-03 and from a design file
(`gemini-code-1788468625606.html`), which arrived after the board was written.
Running these through the loop means a `leader` turn to decompose four
screens into checkpoints first, and that turn costs a full agent budget before
any code exists.

**The loop is serial by construction, and this work is not.** One
`implementer` holds one checkpoint. The four current lanes touch disjoint
directories (`features/script` and `features/ask` here;
`features/tracker`, `features/projects`, `api/`, `state/` elsewhere). §13's
own rule — "parallel writers are for genuinely disjoint file sets" — is
satisfied, and running them serially would pay four times the wall-clock for
the same tokens.

**The reviewer role costs a budget for what a gate already proves.** §13 says
outright: "Anything one Bash call answers" must not be delegated, and
`./.claude/init.sh check` is one call covering seven gates, 793 backend tests
and now 392 web tests. A separate `reviewer` agent re-reads the diff on its
own context window to report the same numbers. The measured session on
2026-09-05 that hit the limit with two workers killed at 429 spent 49% of its
usage on `general-purpose` agents and four of its nine subagents on reading
files and reporting back.

**The loop assumes the human is absent.** Its termination guarantees exist so
an unattended session cannot spin forever. This work has a human reading every
report and correcting mid-turn. The machinery that bounds an unattended loop
buys nothing when a person is already the bound.

---

## 3. What the loop is better at, and what it costs to skip it

This is the part worth reviewing, because the parallel topology gives up real
things.

| | The loop | Briefed parallel workers |
|---|---|---|
| Independent review of a diff | Yes, a separate agent with its own reading | No, the worker checks its own work against the gates |
| Bounded retries | `Attempts` caps at 3, `BLOCKED` is terminal | None; a stuck worker reports and stops |
| Durable record of why | Every `D`-numbered decision lands in `CHECKPOINTS.md` | Commit messages and the worker's report |
| Wall-clock for disjoint work | One lane at a time | All lanes at once |
| Token cost per unit of code | Leader turn + implementer + reviewer, per checkpoint | One worker, plus the shared preamble read once per lane |
| Behaviour when the human is away | Terminates on its own | Stops at the first thing the brief did not cover |
| Merge risk | One writer, so none | Real; four branches merge into `develop` in some order |

The two losses that matter:

**Nobody but the author read this diff.** The gates catch a layer violation, a
dead CSS class, a missing test, a type error. They do not catch a component
that renders the wrong thing correctly, or a test that asserts on its own
fixture rather than on behaviour. On this branch that risk is concrete: the
`ScriptPaper` tests are written by the same worker that wrote `ScriptPaper`.

**The decisions are in commit messages rather than on the board.** The
toolbar decision on this branch — formatting controls drawn and disabled,
because the API has no endpoint that writes a script back — is recorded in a
commit body and in a docstring. The next person to ask "why is Bold greyed
out" has to find it there. In the loop it would be a `D`-numbered entry that
every future agent reads.

Both are recoverable. The first by running `judgment-day` or the four-lens
review over the merged branch, which is a review action rather than a change
of topology. The second by copying the decision into `CHECKPOINTS.md` when the
lane merges.

---

## 4. Is it better

For this work, yes, on cost and wall-clock, and only because two conditions
hold: the file sets are genuinely disjoint, and a human is reading the
reports. Remove either condition and the loop is the better machine.

The honest version of the trade is that the parallel topology is not a
replacement for the loop. It is the loop with the `leader` turn replaced by a
human-written brief and the `reviewer` turn replaced by the gates plus that
same human. It works while the human is there. `AGENT.md` §6's guarantees are
about what happens when they are not.

A rule that would settle it, if the user wants one in `AGENT.md`:

- Work that already has checkpoints on the board runs through the loop.
- Work that arrives as a design the board has never seen runs as briefed
  lanes, and lands its decisions on the board when it merges.
- Any lane that touches a file another lane touches goes back to the loop,
  because the disjointness that justifies the parallel topology is gone.

---

## 5. State of the project, 2026-09-05

`develop` was green at 7 gates, 793 backend tests, 315 web tests before this
lane. On `feature/script-review` the same command reports 7 passed, 0 failed
with 392 web tests.

**Four lanes in flight**, each branched from `develop`:

| Branch | What it carries |
|---|---|
| `feature/script-review` | The script notepad and the Ask screen (this lane) |
| `feature/web-product-ui` | The project overview with the tracker grouped by state |
| `feature/web-dashboard` | Merged already: the cleared ring, the analyze screen, the projects landing |
| `feature/api-partition`, `feature/data-plane` | Merged already: the API split into six domains, and the evidence that outlives a run |

**What is real on the server.** `GET /api/projects/{id}/scripts/{script_id}`
serves scenes, findings and span offsets, persisted, surviving a reload.
Offsets are computed server-side in the domain (ADR 0015) and counted in
Unicode code points. The tracker, the analysis job, the questions endpoint and
the bible are all served. There is no endpoint that writes a script back,
which is why the formatting toolbar on the script screen is drawn disabled.

**What the board still says is open.** 19 `TODO`, 2 `IN_REVIEW`, 1 `BLOCKED`.
The `BLOCKED` one waits on a Grafana credential no agent can mint. The board
has not been updated with the four screens now being built, which is the
bookkeeping debt this topology creates and the thing to fix first if the loop
is resumed.

**Known stale copy outside this lane.**
`web/src/features/item/ItemDetailPanel.tsx:97` still says the analysis lives
in the session only. It does not; it is read back on mount. That file belongs
to another lane's file set, so this lane reports it rather than fixing it.
