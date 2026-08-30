# WRITING.md — Prose Contract for ClearCut

Companion to `AGENT.md`. That file governs code; this one governs prose —
Markdown docs, `README.md`, PR/commit descriptions, and any narrative text an
agent writes. It does not cover source code, identifiers, or code comments.

Adapted from [petergyang/no-ai-slop](https://github.com/petergyang/no-ai-slop)
(MIT license), condensed to what a reviewer can check in a diff.

---

## 0. Scope

Applies to reader-facing prose: `docs/resources/`, `docs/plan/`, `README.md`, commit and
PR descriptions, and narrative text shipped in the product. The planning
documents in `docs/plan/` are deliverables in their own right, so §4 applies to them
at blocking weight.

Does not apply to specifications — `AGENT.md`, `CHECKPOINTS.md`, and the agent
definitions in `.claude/agents/`. Those are instructions, not narrative. They
repeat one exact term on purpose where §2 would ask for variety, and they are
written to be scanned by an agent under load rather than read through. §3's
demand for concreteness still binds them.

---

## 1. Banned words

delve, foster, leverage, utilize, facilitate, empower, streamline, robust,
cutting-edge, paradigm shift, game changer, this is huge, this changes
everything, tapestry, realm, beacon, multifaceted, meticulous, intricate,
paramount, transformative, elevate, embark, supercharge, harness,
ever-evolving.

**Often-empty adverbs** — cut unless they carry real emphasis or uncertainty:
just, literally, honestly, simply, actually, truly, fundamentally,
importantly, crucially, inherently, inevitably.

**Often-empty phrases** — cut when they delay the point: it's worth noting,
it's important to note, at the end of the day, when it comes to, at its core,
in today's world, in the age of, the reality is, the truth is, in terms of,
with regard to, in order to, going forward.

## 2. Patterns to cut

- **Binary contrasts** — "It's not X. It's Y." State Y directly.
- **Throat-clearing openers** — "Here's the thing," "Let me be clear." Cut
  and state the point.
- **Faux-insight setups** — "What nobody tells you," "The part everyone
  misses." Make the claim stand on its own.
- **Colon reveals** — a noun phrase, a colon, a lowercase dramatic reveal
  ("The best part: it learns."). Rewrite as a plain sentence.
- **Superficial analysis** — trailing `-ing` clauses that gesture at meaning
  ("highlighting the team's commitment"). Say what actually happened.
- **Importance puffery** — "marks a pivotal moment," "a testament to." State
  the fact, let the reader judge.
- **Interpretive metadiscourse** — "That last part matters more than it
  sounds," "As you can see." Delete or replace with actual support.
- **Weasel attribution** — "experts agree," "studies show." Name the source
  or cut the claim.
- **Fake-strong verbs** — prefer "is"/"has" when clearer than "serves as."
- **Synonym cycling** — repeat the right word instead of rotating synonyms
  for style.
- **Negative listing** — "Not a X. Not a Y. A Z." Just say Z.
- **Dramatic fragmentation** — "X. And Y. And Z." Use complete sentences.
- **Robotic rhythm** — repeated sentence shapes, stacked punchy fragments.
- **Rhetorical setups** — "What if I told you...", self-answered
  question/answer pairs.
- **Fake-profound kickers** — a closing aphorism or mic-drop line. Delete it;
  end on the clearest concrete sentence already in the draft.
- **Summary-recap endings** — "In conclusion," "Ultimately." End on the last
  concrete point or next action instead.
- **Formatting slop** — emoji anywhere (headings, body text, labels, UI copy;
  status values are words like BLOCKED/IN_PROGRESS/CLEARED, never colored
  circles), decorative mid-sentence bold, bullets where two sentences of prose
  read better, headers over two-sentence sections.
- **Em dashes as a rhythm crutch** — none in short copy; at most 1–2 in a
  long doc, only where they clearly beat a comma or period.

## 3. Editing principles

- Preserve the writer's real voice — vocabulary, bluntness, digressions.
  Don't smooth every paragraph into the same tidy register.
- Make the minimum effective edit. Leave strong human sentences alone.
- Lead with the point; cut setup that adds nothing.
- Active voice — don't let inanimate things do human verbs.
- Be concrete: names, numbers, dates, mechanisms beat abstractions
  ("cut deploy time from 40 minutes to 4," not "improved efficiency").
- **Portability test** — if a sentence could move unchanged to another
  product or company, it's filler. Cut it or make it specific.
- Show, don't tell — let facts and examples carry the point instead of
  labeling it "important" or "surprising."

## 4. Reviewer checklist

Run this whenever a diff touches `docs/resources/`, `docs/plan/`, `README.md`, or other
prose:

- [ ] No banned word or empty filler phrase from §1, unless quoted as an
      example.
- [ ] No named pattern from §2 present in the new/changed text.
- [ ] Claims are specific (names, numbers, mechanisms) — none fail the
      portability test.
- [ ] Active voice used where a human or system is the actual actor.
- [ ] No fake-profound kicker or summary-recap ending.
- [ ] Em dashes, if present, are sparing and load-bearing.

**When an unchecked box blocks.** Prose is gated, but it must not spin the loop
(`AGENT.md` §6), so the weight depends on whether the prose is the work:

- **Blocking** — the checkpoint's own acceptance criteria name the text (a
  README, a doc, a PR description). The prose *is* the deliverable, so an
  unchecked box carries the same weight as a failing `pytest` or `ruff` gate.
- **Non-blocking** — the diff touches prose only in passing. The reviewer
  records the finding and the leader raises it as its own checkpoint. Style
  never sends a code checkpoint back for another attempt.
