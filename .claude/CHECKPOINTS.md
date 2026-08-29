# CHECKPOINTS.md — Loop State

The only shared state between `leader`, `implementer`, and `reviewer`.
Rules and status machine: `.claude/AGENT.md` §6–§7.

**Editing rules**
- One checkpoint = one behaviour, implementable and reviewable in one turn.
- Only the agent named in the status machine may change a `Status`.
- Never delete a checkpoint. Move terminal ones (`DONE`, `SUPERSEDED`) to
  *Archive* at the bottom.
- `Attempts` is `n/3`. At `3/3` the checkpoint becomes `BLOCKED`.
- `BLOCKED` never returns to `TODO`. The `leader` either marks it `SUPERSEDED`
  and creates smaller `Depth: 1` checkpoints, or stops for a human.
- `Depth` is `0` for a planned checkpoint, `1` for one born from a split. A
  `Depth: 1` checkpoint is never split again — it escalates to a human.

**Block template** — copy verbatim:

```
### CP-000 — <imperative, one behaviour>
- Status: TODO
- Attempts: 0/3
- Depth: 0
- Layer: domain | application | adapters | tests | infra
- Depends on: - | CP-00x
- Acceptance:
  - [ ] <observable behaviour, phrased as a test>
  - [ ] <failure path>
- Files: <expected paths>
- Notes: -
```

---

## Goal

_No active goal. The `leader` writes it here, in one sentence, before adding
checkpoints._

---

## Active

_None yet. Run `leader` to decompose the goal._

---

## Archive

_Terminal checkpoints (`DONE` / `SUPERSEDED`), newest first._
