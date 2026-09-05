# Resume Cut Work

Paste this prompt into a session that has to pick up work this repository lost
mid-flight, whether to a rate limit, a crash, or a context reset. It assumes
`.claude/CHECKPOINTS.md` carries status rows, that work may live in more than
one worktree, and that the project's gates can be run before a commit. The
prompt runs four phases and stops between the plan and the code.

## The prompt

```
Resume the work that got cut off in this repo and take it as far as it goes today.

You have the diagnosis from the previous analysis in this conversation. If you
don't (fresh session), re-derive it first: mem_context, mem_search, then
`git log --oneline -20`, `git status`, `git branch -r`, `git worktree list`,
and the non-DONE rows of .claude/CHECKPOINTS.md in every worktree.

PHASE 1 - PLAN. Do not write code yet.

Produce a plan for today only, ordered by unblocking value, not by checkpoint
number. For each work unit give me:
  - the checkpoint ID and which worktree/branch it lives in
  - what "done" means as an observable fact (a passing test, a pushed ref, a
    closed status), not "implemented X"
  - its dependencies, and whether they are satisfied right now
  - the single commit it produces

Rules for what goes in the plan:
  - Anything BLOCKED on a human (external signup, a credential, a webhook URL,
    a decision only I can make) is NOT in today's plan. List those separately
    under "Not today - waiting on me" with the exact action I have to take.
  - Do not start a new goal while an earlier one still sits IN_REVIEW. Close
    or explicitly defer the IN_REVIEW items first, and say which you chose.
  - Recover cheap lost ground before starting new work. An unexecuted push, an
    uncommitted-but-passing change, or an unrecorded status is worth more than
    the next TODO.
  - Time-box it to one working session. State plainly what you are deferring
    and why - I would rather see three things finished than nine started.

PHASE 2 - CONFIRM. Present the plan, then STOP.

Ask me only about the real forks: anything where two readings lead to
materially different work, or where the previous session left an open
question. One question at a time. Do not proceed on assumptions.

PHASE 3 - IMPLEMENT. Only after I approve.

  - Work the plan in the stated order. One work unit, one commit.
  - Conventional commits. Stage by explicit path - never `git add -A`.
  - Run the project's gates before each commit and paste the real output. Never
    call something green without the run behind it. If a gate fails, fix it or
    stop; do not commit around it.
  - Update the checkpoint status in .claude/CHECKPOINTS.md as each unit lands,
    in the same commit as the work.
  - Push only what I approved pushing, on the branch I approved.
  - If you hit something that was not in the plan and is not trivial, stop and
    tell me rather than expanding scope.
  - If a step turns out to be blocked mid-flight, finish every other unit in
    full and report what you left out and why. Scaling the plan down is my
    call, not yours.

PHASE 4 - REPORT.

  - What landed, with commit hashes and the gate output that proves each one.
  - What is still open, and whether it is open on you or on me.
  - The single next action for the next session.
  - Save a session summary to memory before the final message, but the summary
    is bookkeeping - the report is the answer.

No emoji anywhere. Textual status values only.
```

## Why these guardrails

Two of the rules above are not general advice. Each one is in the prompt
because its absence already cost this repository a session.

1. Recover cheap lost ground first. On 2026-09-04 a session was cut between
   the instruction "push it" and its execution. The branch
   `feature/api-by-domain` went unpushed with 103 commits on one disk, and
   seven files of finished, gate-green work sat uncommitted for two days. None
   of that needed new code, only the commands nobody ran. Unlanded work is the
   most common form of loss here and the cheapest to recover, so the plan
   collects it before it opens a new TODO.

2. Phase 2 hard-stops for approval. A previous run read the word "analyze" and
   dispatched nine agents before the diagnosis had been confirmed. The stop
   makes the plan something I read before it is executed, instead of something
   I find out about from the results.
