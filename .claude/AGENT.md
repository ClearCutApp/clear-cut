# AGENT.md — Engineering Contract for ClearCut

The single source of truth for **how** work is done in this repo. Every agent
(`leader`, `implementer`, `reviewer`) and every human reads this file first.
`CHECKPOINTS.md` is the state; this file is the rules.

---

## 1. Project

**ClearCut / IP Guardian** — an agentic script-clearance engine for independent
film production. It extracts IP entities from a screenplay (copyright,
trademarks, music, personality rights, locations, conexity rights), resolves
rights holders per jurisdiction, and audits narrative continuity against a
project bible.

Stack: Python 3.11+, Flask, Google GenAI (Gemini), Parallel Search API,
ClickHouse. Reference docs live in `docs/resources/`; planning documents live in
`docs/plan/`.

This file governs code. Its companion `.claude/WRITING.md` governs prose — docs,
`README.md`, commit and PR descriptions — and exempts specification files like
this one.

Prose in this repo — docs, `README.md`, PR/commit text — follows
`.claude/WRITING.md`, not this file. That contract is kept separate from
this one on purpose: this file is about code, `WRITING.md` is about prose.

---

## 2. Architecture

Three layers. Dependencies point **inward only**.

```
adapters  ──►  application  ──►  domain
(I/O)          (use cases)       (rules)
```

```
src/clearcut/
  domain/         pure business rules. stdlib only. no I/O, no framework.
  application/    use cases + ports (typing.Protocol). imports domain only.
  adapters/       gemini/, parallel/, clickhouse/, http/. implements ports.
  composition.py  the ONE place that wires concrete adapters into use cases.
tests/
  unit/           domain + application, with hand-written fakes. no network.
  live/           adapters against the real service, never a fake. marked
                  `live`, deselected by default, skipped without credentials.
  integration/    collection probe only — it catches a missing __init__.py.
```

**Hard rules**

1. `domain/` imports nothing from `application/` or `adapters/`, and no
   third-party package. If it needs the time or a random number, it takes it
   as an argument.
2. `application/` defines the ports it needs (`Protocol`), never imports
   `flask`, `google.genai`, `clickhouse_connect`, or `requests`.
3. `adapters/` translates: external shapes and errors in, domain types and
   domain errors out. Adapters hold no business rules.
4. Wiring happens only in `composition.py`. No global singletons, no service
   locator, no DI framework — plain constructor injection.
5. A use case is one behaviour with one public entry point (`execute`), or a
   plain function when it holds no collaborators.

---

## 3. Design principles, applied concretely

**SOLID** — as checks, not slogans:
- **SRP** — one reason to change. A module that both parses Gemini JSON *and*
  decides risk level is two modules.
- **OCP** — new jurisdictions / new IP categories arrive as data or a new port
  implementation, never as another `elif` in a use case.
- **LSP** — every implementation of a port satisfies the same contract test.
- **ISP** — ports are narrow. `RightsHolderSearch.find(entity, territory)` —
  not a 12-method `ExternalServices` interface.
- **DIP** — use cases depend on ports they declare; adapters depend on those
  ports. Never the reverse.

**GRASP** — for placing behaviour:
- *Information Expert* — logic lives with the data it needs. Risk level is a
  method on the IP item, not a helper in the Flask route.
- *Creator* — the aggregate creates its parts.
- *Low coupling / High cohesion* — the deciding tiebreak in any review.
- *Controller* — the use case is the controller; the Flask route only maps
  HTTP ↔ use-case input/output.
- *Pure Fabrication* — allowed for genuine infrastructure concerns only.

---

## 4. Anti-over-engineering rules

These override the section above whenever they conflict. Simplicity wins.

- **A port only for a real I/O boundary** — network, database, filesystem,
  clock, randomness. Never for in-process code.
- **No interface with a single implementation** unless it crosses a boundary
  above.
- **No abstraction for one caller.** Duplicate twice; extract on the third.
- **Banned until a checkpoint proves the need:** DI containers, event buses,
  CQRS, event sourcing, mediators, repository-of-repositories, generic
  `BaseService`/`BaseManager`, plugin registries, custom metaclasses.
- **No config for a value that has never changed.**
- **YAGNI** — build exactly what the current checkpoint's acceptance criteria
  require. Anything else becomes a new `TODO` checkpoint, not code.
- Prefer a function to a class. Prefer a dataclass to a class with getters.
- **Size guides** (soft, argue if wrong): function ≤ 30 lines, file ≤ 300
  lines, ≤ 4 constructor parameters, nesting ≤ 3.

---

## 5. Testing

Non-negotiable: **no production code ships without a test that would fail
without it.**

- **TDD order** — write the failing test, watch it fail, make it pass, refactor.
- Unit tests use hand-written fakes implementing the port. No `unittest.mock`
  patching of internals; patching is a coupling smell.
- Unit tests do no network, no clock reads, no filesystem writes.
- Every use case: one happy path + at least one failure path.
- Every domain rule: its boundary cases.
- Every port: one contract test that all its implementations run.
- Tests name the behaviour: `test_flags_unlicensed_music_as_critical_risk`,
  not `test_analyze_2`.
- **A checkpoint that introduces or changes an adapter is not `DONE` without a
  `tests/live/` test that reaches the real service**, and its acceptance
  criteria must name that test. §4 binds an implementer to the acceptance
  criteria, so a requirement stated only here is a requirement an implementer
  may skip.
- **A live test asserts on a value only a real response carries.** Not "no
  exception was raised" — a fake raises no exception either. A token count, a
  citation URI, a server-assigned id, a digest the service stored and returned.
  If the assertion would still hold against a hand-written fake, it proves
  nothing that the unit test did not already prove.
- Gates that must pass before a checkpoint is `DONE`:
  `pytest -q` green, `ruff check .` clean, `ruff format --check .` clean,
  `mypy src tests infra main.py` clean, and for an adapter checkpoint
  `./.claude/init.sh live` green with its credentials present.

**Why this section grew.** Fifty-four checkpoints closed with 477 green tests,
`init.sh check` at `6 passed, 0 failed`, and not one adapter had ever contacted
the service it wraps. Every criterion above the live bullets is satisfiable with
a hand-written fake, so "done" and "works" were unrelated — and two identifier
bugs guaranteed to fail on the first real call sat in `main` the whole time,
invisible to all of it. The live tier is the only gate that can fail because a
service is unreachable.

---

## 6. The loop

Three roles, one shared state file, a bounded number of turns.

```
                ┌──────────────────────────────────────────────┐
                ▼                                              │
  ┌────────┐   plan    ┌─────────────┐  diff  ┌──────────┐     │
  │ leader ├──────────►│ implementer ├───────►│ reviewer │     │
  └───┬────┘           └─────────────┘        └────┬─────┘     │
      │                       ▲                    │           │
      │                       └── CHANGES_REQUESTED┘ (≤3)      │
      │                                             │          │
      │                            PASS ────────────┘          │
      │◄─── BLOCKED (supersede once, or stop for a human) ───────┘
      │
      ▼
  all checkpoints DONE → report to human
```

**Conductor.** The main Claude session (or a human) is the conductor: it reads
`CHECKPOINTS.md`, dispatches the next agent, and writes nothing else. Subagents
do not dispatch each other — all coordination goes through `CHECKPOINTS.md`, so
the loop behaves identically whether a human, a script, or the main session is
driving it.

**Turn order**

1. `leader` — decomposes the goal into checkpoints in `CHECKPOINTS.md`. Writes
   no source code.
2. `implementer` — takes exactly **one** checkpoint with status `TODO`, sets it
   `IN_PROGRESS`, implements it test-first, sets it `IN_REVIEW`.
3. `reviewer` — reviews that checkpoint's diff, runs the gates, returns a
   verdict. Writes no source code.
4. On `PASS` → status `DONE`, conductor moves to the next `TODO`.
   On `CHANGES_REQUESTED` → status `TODO`, `Attempts` +1, back to step 2.
   On `BLOCKED`, or `Attempts` reaching 3 → status `BLOCKED`, back to `leader`.
5. When no checkpoint is `TODO` / `IN_PROGRESS` / `IN_REVIEW`, the loop ends
   and the conductor reports to the human.

**Termination guarantees** (why this cannot spin forever)

- `Attempts` is capped at `3/3` per checkpoint. The 3rd rejection sends it to
  `BLOCKED`.
- **`BLOCKED` is terminal for that checkpoint.** The `leader` never returns it
  to `TODO`. It either supersedes it — marking it `SUPERSEDED` and creating
  strictly smaller checkpoints at `Depth: 1` — or leaves it `BLOCKED` and stops
  for a human. This removes the only unbounded back-edge in the machine.
- **One generation of splitting.** Only a `Depth: 0` checkpoint may be
  superseded. A `Depth: 1` checkpoint that blocks stops the loop for a human.
  The checkpoint graph therefore grows at most one level.
- Only **blocking** findings send work back. Non-blocking findings become new
  `TODO` checkpoints — polish never re-opens a passing checkpoint.
- `leader` may add checkpoints only for a new human goal or a `BLOCKED`
  checkpoint, never in response to a `PASS`.
- The only cycle in §7 is `IN_REVIEW → TODO`, guarded by `Attempts`. Every other
  path ends at a terminal status (`DONE` or `SUPERSEDED`).
  `./.claude/init.sh verify` proves this mechanically from the table itself.

---

## 7. Status machine

| From          | To                                  | Who         |
|---------------|-------------------------------------|-------------|
| `TODO`        | `IN_PROGRESS`                       | implementer |
| `IN_PROGRESS` | `IN_REVIEW`                         | implementer |
| `IN_PROGRESS` | `BLOCKED`                           | implementer |
| `IN_REVIEW`   | `DONE`                              | reviewer    |
| `IN_REVIEW`   | `TODO` (+1 attempt)                 | reviewer    |
| `IN_REVIEW`   | `BLOCKED`                           | reviewer    |
| `BLOCKED`     | `SUPERSEDED` (split once, Depth 0)  | leader      |

Terminal statuses: `DONE`, `SUPERSEDED`.

Every other status must have a way out. There is no edge back out of `BLOCKED`
other than a one-time split, and none at all from a `Depth: 1` checkpoint —
that is what bounds the loop.

Any other transition is a bug — stop and report it.

---

## 8. Handoff contracts

Each agent ends its turn with exactly this block, verbatim keys, nothing after it.

**leader**
```
ROLE: leader
CHECKPOINTS_ADDED: CP-004, CP-005
NEXT: implementer CP-004
NOTES: <one line, or ->
```

**implementer**
```
ROLE: implementer
CHECKPOINT: CP-004
STATUS: IN_REVIEW | BLOCKED
TESTS: <command> -> <pass/fail counts>
FILES: <paths touched>
NEXT: reviewer CP-004
```

**reviewer**
```
ROLE: reviewer
CHECKPOINT: CP-004
VERDICT: PASS | CHANGES_REQUESTED | BLOCKED
EVIDENCE: pytest -> ... | ruff -> ... | live -> ... (or n/a)
BLOCKING: <n>
DEFERRED: <new checkpoint titles, or ->
NEXT: implementer CP-004 | leader CP-004 | done
```

---

## 9. Definition of Done (a checkpoint)

- [ ] Every acceptance criterion checked off.
- [ ] A test exists that fails without the change.
- [ ] `./.claude/init.sh check` green — all six gates: `ruff check`,
      `ruff format --check`, `mypy src tests infra main.py`, `pytest -q`, and
      the `web/` typecheck and test suite.
- [ ] **Adapter checkpoints only:** `./.claude/init.sh live` green with
      credentials present, and its assertion is one a fake could not satisfy
      (§5). A live test that passes without credentials is testing a fake.
- [ ] Layer rules (§2) hold — verified by import direction.
- [ ] No item from §4 introduced.
- [ ] Prose in the diff satisfies `.claude/WRITING.md` (§4 checklist, at the
      weight that file defines).
- [ ] `CHECKPOINTS.md` updated with the outcome.

---

## 10. Running it

```bash
./.claude/init.sh          # bootstrap the toolchain, then verify (run this first)
./.claude/init.sh verify   # prove the loop is well-formed — safe in CI
./.claude/init.sh check    # ruff + pytest
```

Then drive the loop from a Claude Code session:

```
Use the leader agent to plan: <goal in one sentence>
Use the implementer agent on CP-001
Use the reviewer agent on CP-001
```

The session is the conductor: it reads the handoff block each agent returns
(§8), follows its `NEXT`, and stops when a reviewer returns `NEXT: done` or a
checkpoint is `BLOCKED` for a human. State lives in `CHECKPOINTS.md`, so the
loop resumes correctly in a new session, or under a human, from that file alone.

`verify` is not decoration — it reads the §7 table and proves there is exactly
one cycle in the machine, that it is guarded by the attempt counter, and that
every other path reaches a declared terminal. Change §7 and the proof re-runs.

---

## 11. Relationship to gentle-ai

[gentle-ai](https://github.com/Gentleman-Programming/gentle-ai) is installed
globally (`~/.claude/`), so its agents, skills and slash commands are visible in
every project on this machine — including this one. It is an ecosystem
configurator, not a scaffold: it ships no application structure.

**The split of ownership is not negotiable, because both define a process.**

| Concern | Owner |
|---|---|
| Process: what gets built, in what order, and who approves it | **this repo** — §6, `CHECKPOINTS.md` |
| Architecture and testing rules | **this repo** — §2–§5 |
| Cross-session memory (Engram) | gentle-ai |
| Skills library (`work-unit-commits`, `cognitive-doc-design`, …) | gentle-ai |
| Persona, `context7` MCP | gentle-ai |

**Rules**

1. **Do not use the SDD pipeline in this repo.** `/sdd-init`, `/sdd-new`,
   `/sdd-apply`, `/sdd-verify` and the `sdd-*`, `review-*`, `jd-*` agents
   implement a second, competing loop. Running both splits the state between
   SDD artifacts and `CHECKPOINTS.md`, and neither is then trustworthy. This
   repo's loop is `leader → implementer → reviewer`, full stop.
2. **Engram memory is read by all three agents, written by one.** All three may
   `mem_search` / `mem_get_observation` for recall across sessions. Only the
   `leader` may `mem_save` / `mem_update` — a reviewer or implementer that
   records its own conclusions is writing state nobody reviewed, which is the
   same reason the reviewer cannot `Write` code. The implementer and reviewer
   surface anything worth keeping through `Notes`; the leader decides.

   Memory is recall, never loop state. `CHECKPOINTS.md` remains the only place a
   checkpoint's status lives, because the loop must resume from a file a human
   can read and edit.
3. **Skills are available and encouraged.** Where a skill conflicts with §2–§5,
   **AGENT.md wins** — a skill cannot authorise an untested change, a layer
   violation, or an abstraction banned by §4.
4. **Switching to SDD is a deliberate migration, not a drift.** If SDD should
   own the process, delete `.claude/agents/{leader,implementer,reviewer}.md` and
   say so here. Never run both.

`./.claude/init.sh verify` enforces rules 1 and 4 mechanically.

---

## 12. Skill allowlist

§11 rule 3 says skills are encouraged. This section says **which** skills, because
the machine-wide index cannot answer that question.

`.atl/skill-registry.md` is generated by the `gentle-ai` CLI, which scans every skill
directory on this machine and writes the union into every project. It takes no scope
flag. A `gentle-ai skill-registry refresh` therefore re-widens that file to ~41 rows,
23 of them Ethereum and Solana skills. **This list is authoritative; the registry is
not.** When they disagree, this list wins.

**The twelve skills in scope for ClearCut**

| Skill | Applies to |
|---|---|
| `cognitive-doc-design` | `docs/`, `README.md`, architecture and review-facing prose |
| `design-taste-frontend` | The Compliance Tracker dashboard |
| `redesign-existing-projects` | Dashboard revisions, once a UI exists |
| `branch-pr` | Opening PRs |
| `chained-pr` | Splitting a change over ~400 lines |
| `work-unit-commits` | Commit decomposition |
| `issue-creation` | Filing GitHub issues |
| `systemic-issue-triage` | Triage by root class |
| `comment-writer` | PR and issue replies |
| `judgment-day` | Blind dual review |
| `skill-creator` | Authoring a project skill |
| `skill-improver` | Auditing a project skill |

**Rules**

1. **A skill absent from the table above is not loaded**, whatever
   `.atl/skill-registry.md` lists. Adding one is an edit to this file, made by a
   human, not a decision an agent takes mid-task.
2. **Select on a skill's description, never its name.** Five excluded skills carry
   generic names and Ethereum-specific bodies:

   | Name reads as | Body actually contains |
   |---|---|
   | `testing` | Foundry unit, fuzz, fork and invariant tests |
   | `security` | Solidity vulnerabilities, pre-deploy audit checklist |
   | `qa` | Scaffold-ETH 2 dApp pre-ship checklist |
   | `tools` | Ethereum RPCs, block explorers, Hardhat |
   | `standards` | ERC-20, ERC-721, ERC-1155, ERC-4337 |

   `~/.claude/skills/_shared/skill-resolver.md` tells delegators to consult the
   registry before every subagent launch involving testing or reviewing. Matching
   `testing` or `security` by name there hands a Python subagent a Solidity
   checklist, and the subagent has no way to detect the mismatch.
3. **This project's testing and security rules are §5 and §2 of this file.** No
   external skill supplies them.
4. **`.atl/` is machine-local and gitignored.** Never commit it, and never cite it
   as evidence in a PR.
