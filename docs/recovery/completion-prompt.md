# Continue ClearCut to verified completion

Use this prompt in an agent runtime with access to the existing workspace:

```text
Finish the unfinished ClearCut product in this repository. Continue through
implementation and verification; do not stop after a review or plan.

Start with current user instructions and root AGENTS.md, then read
 docs/recovery/specification.md
 docs/plan/adr/architecture/0016-production-recovery.md
 docs/recovery/situation-2026-09-07.md
 docs/recovery/checklist.md
Recover relevant Engram decisions and compare them against the current code and
Git state. Preserve all staged, unstaged and untracked work. Keep one writer.

Inventory docs, agent instructions, workflows and saved prompts. Read relevant
historical material to resolve contradictions, but do not execute superseded
.claude checkpoint/role loops or assume old status counts are current. The approved
specification and ADR 0016 define the product; current code defines what exists;
dated executable evidence defines what is verified. Record remaining discrepancies
and the next bounded work in the situation/checklist without shrinking scope.

Implement the highest-priority unfinished end-to-end slice. Preserve Flask,
React/Vite and hexagonal dependencies. Producers and screenwriters need working
private workspaces, screenplay import/edit/revisions, durable analysis, cited
findings, evidence/clearance workflow, reports, teams, voice and accessible EN/ES UI.
Preserve every required Google Cloud, Parallel, ClickHouse, webhook and Grafana
integration. Finish real adapters and wiring rather than adding demos or logos.
Use the existing cinematic landing and navy/emerald references; expose real data.

Run meaningful changed-behavior tests and applicable repository checks. Use the
bounded deployed acceptance CLI and guide for authorized synthetic cloud work.
Tokens stay in environment, receipt intent precedes mutations, and unknown outcomes
are never blindly retried. Missing setup, pending jobs and skipped live tests are
unverified. Adapter success is not full application proof; structural citations are
not semantic legal correctness. Do not infer permission to activate schedules,
migrate legacy ownership, send outreach or erase data.

Continue independent authorized work when an external dependency blocks one slice.
Keep the checklist, dated evidence and Engram current. Report concrete changes,
exact verification and remaining blockers concisely. Do not claim release readiness
until every approved deployed acceptance criterion has evidence.
```
