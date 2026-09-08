> Historical reference. Recovery specification and workflow in `AGENTS.md` and
> `docs/recovery/` supersede conflicting instructions and completion claims.

# CHECKPOINTS.md — Loop State

The only shared state between `leader`, `implementer`, and `reviewer`.
Rules and status machine: `.claude/AGENT.md` §6–§7.

**Editing rules**
- One checkpoint = one behaviour, implementable and reviewable in one turn.
- Only the agent named in the status machine may change a `Status`.
- Never delete a checkpoint. Move terminal ones (`DONE`, `SUPERSEDED`) to
  *Archive* at the bottom.
- `Attempts` is `n/3`, counting `CHANGES_REQUESTED` verdicts and nothing else
  (AGENT.md §6 step 4). A checkpoint that passes its first review stays at
  `0/3`. At `3/3` the checkpoint becomes `BLOCKED`. Settled by D49; four
  archived blocks predate that ruling and are left as they were written.
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

Build ClearCut per `docs/plan/sdd.md`: a Flask JSON service that turns an uploaded
screenplay into cited, jurisdiction-grounded clearance findings and a versioned
tracker, with a React SPA over it.

---

## Decisions

Settled on 2026-08-30, before CP-006 through CP-010 dispatch to parallel
implementers. Each entry answers a question that was either a contradiction in
the checkpoint text or a question the user asked directly. The reasoning is
here because the next person to read this file is the one who will want to
reopen it, and a decision without its reasoning gets re-litigated.

**D1. `Citation` stays in `clearcut.domain.finding`; CP-010's criterion is
reworded instead.** CP-010 forbade importing that module while its own
criterion 2 required returning a `RightsClaim` carrying `Citation`s. Both
`Category` and `Citation` report `__module__ == "clearcut.domain.finding"`, so
the two criteria could not both hold. Moving `Citation` to its own module would
change `application/ports.py`'s import line, and that file was frozen by
CP-005's review precisely so five concurrent implementers build against one
shape. The criterion is narrowed to what it evidently meant — the adapter does
not import `RiskLevel` — which is the smallest change (AGENT.md §4) and touches
no port signature. No new checkpoint.

**D2. Adapters receive a resolved `Jurisdiction`; resolving a raw code belongs
to the caller.** `LegalGrounding.ground` and `RightsResearch.find` both take a
`Jurisdiction` value object, so an adapter never sees a code and cannot
meaningfully raise `UnknownJurisdiction`. Re-resolving `jurisdiction_for(j.code)`
inside the adapter to satisfy the old criterion would be validating something
already validated. CP-009's failure path is rewritten to one the adapter genuinely
owns: a blank `corpus_prefix` is refused before any client call, because
`jurisdiction: ANY("")` returns every jurisdiction rather than failing — the same
silent-unfiltered-results failure the console-only step in D6 describes. The
`UnknownJurisdiction` path moves to phase 4, where the route holds the raw
`jurisdiction_code` and maps that error to HTTP 400. Port signatures unchanged.

**D3. mypy, strict on `src/clearcut`, landing before the five adapters as
CP-012.** `runtime_checkable` proves method presence only: an adapter whose
`extract` takes its two arguments in the other order passes every check this
repo runs today. mypy over pyright because the backend gate is already a pure
Python venv (`.claude/init.sh` installs pytest and ruff into it) and pyright
would pull a Node toolchain into a root that has none — `web/` owns npm, and
keeping that boundary is D5's whole point. Strictness is `strict = true` over
`src/clearcut`, relaxed only for untyped test functions. The mechanism that
catches signature drift is an annotated assignment binding each fake to its
port.

*Edge: before, not alongside.* If it lands alongside the adapters, CP-012's own
"mypy exits 0" criterion becomes hostage to five branches it cannot see, and its
three attempts burn on other people's code. It is one small turn, and CP-011,
CP-013 run in parallel with it, so the wall-clock cost is close to zero.

**D3 amended 2026-08-30, after CP-009 and CP-010 both disproved a third of it.**
The original text claimed the annotated binding makes mypy check "parameter
names, order, and types". Two reviewers proved independently, on separate
adapters and with a minimal probe, that **mypy does not check a Protocol's
positional parameter names** — this is documented mypy behaviour, not a version
bug. Renaming `ground`'s `query` to `question`, and `find`'s `asset_name` to
`name`, each left `mypy src tests` at `Success`, including under
`--no-incremental --cache-dir=/dev/null`. What the binding actually proves,
each verified by mutation rather than by reading:

- **Arity.** A method taking a different number of parameters fails.
- **Parameter types.** Swapping `extract(scenes, jurisdiction)` to
  `extract(jurisdiction, scenes)` produced 11 `arg-type` errors through the
  `checked: SceneExtractor` binding — order is caught *because the types
  differ*, which is why it holds for all five ports and would not hold for two
  same-typed parameters.
- **Return type.** Widening `ground`'s return to `str` fails the assignment.
- **Method presence.** Which `runtime_checkable` `isinstance` also gives.

A rename is caught only at a *keyword* call site through the **concrete**
adapter type (`adapter.ground(query=...)`), never through the port binding.
The consequence is a rule, not a checkpoint (see D15): **use cases call port
methods positionally.**

*The inert-binding pitfall, found in 3 of the 5 adapter tests.* Writing
`assert isinstance(adapter, Port)` **above** `checked: Port = adapter` narrows
`adapter` to `Port` first, so the annotated assignment then binds `Port` to
`Port` and proves nothing at all — the mutation it exists to catch passes.
Correct order is the annotated assignment **first**, the `isinstance` second
(or dropped, since it only re-checks method names). CP-009 and CP-008 are
fixed; `tests/unit/adapters/test_research.py:66-67` still has it backwards and
is repaired by CP-015. A module-level annotated binding with no narrowing at
all — CP-006's `test_document_ai.py:71`, CP-007's `test_extractor.py:80` — is
the cleanest form and cannot regress this way.

**D4. `__init__.py` under every `tests/` directory, folded into CP-012.** Two
test files sharing a basename anywhere in the tree currently kill collection for
the whole suite — `import file mismatch`, zero tests run. `test_client.py` is an
obvious name for two of five parallel implementers to pick independently, and
the breakage would surface only when their branches met. A dispatch note asking
five implementers to coordinate basenames is discipline; package markers are
structure, and structure does not depend on anyone remembering. Folded into
CP-012 rather than given its own checkpoint because both edit `pyproject.toml`,
and two concurrent implementers editing that file is the merge conflict this
decision exists to avoid. It also absorbs the CP-001 backlog item about
`tests/integration/` surviving a commit.

**D5. Keep `src/clearcut/`, `web/`, and a new `infra/` as the three roots. No
rename.** The user asked twice for a DDD-flavored split into backend, frontend,
and infra roots. That separation already holds substantively, and one third of
it is genuinely missing:

- Backend root: `src/clearcut/` — one Python package, with the DDD split
  (`domain/`, `application/`, `adapters/`) *inside* it, which is a stronger
  statement of the architecture than a folder named `backend/` would be. Its
  boundaries are enforced by a test, not by a directory name
  (`tests/unit/test_layer_boundaries.py`).
- Frontend root: `web/` — its own `package.json`, `tsconfig.json`, and
  `vite.config.ts`, never imported by Python, gated by npm commands that
  `./.claude/init.sh check` does not run. ADR 0009, SDD §5.
- Infra root: `infra/` — the one that was missing, and the one D6 builds.

What a rename would buy is the words "backend" and "frontend" in two paths. What
it would cost, eight days from the 2026-09-07 deadline: `pyproject.toml`'s `src`
and `pythonpath`, `.claude/init.sh`'s `$ROOT` handling, the `REPO_ROOT / "src"`
computation the layer guard derives its whole verdict from, the `Files:` line of
every active and archived checkpoint, ADR 0009, SDD §5, and
`docs/plan/infrastructure.md` §9's container build — all mechanical churn across
reviewed, committed artifacts, immediately before five parallel implementers
dispatch, changing no observable behaviour. AGENT.md §4 decides this one.

The rename stays available and stays cheap; it is a `git mv` plus six path
edits, and it is a better move once the demo is recorded than eight days before
it. It is deliberately not filed as a checkpoint, because a checkpoint for work
nobody has asked to happen now is the speculation §4 forbids. If the user wants
it regardless of this reasoning, that is a new goal and one leader turn.

**D6. Idempotent `gcloud` scripts, not Terraform.** Terraform cannot express two
of the seven resources in scope: the Agent Builder agent app has no stable
resource, and marking the `jurisdiction` field Indexable has no API at all. So
Terraform buys partial coverage while adding a second toolchain, a provider
install, and a state backend to a one-shot hackathon provisioning run. The
scripts also start from a better place: `docs/plan/infrastructure.md` is already
written as `gcloud` and `bq` invocations, so CP-013 and CP-014 make existing
prose executable rather than translating it into a new language. Testability
comes from a `--dry-run` mode that prints the commands it would run, which
pytest asserts against without touching a network. ClickHouse Cloud and Grafana
Cloud stay documented, never automated — both are external SaaS signups.

The Cloud Run deploy is deliberately not in CP-013 or CP-014. `gcloud run deploy
--source .` builds a container around a Flask entry point that does not exist
until `composition.py` and the routes land, so a deploy script written now could
not be run, and a script nobody can run is not infrastructure. It is filed under
phase 4 in the Backlog, where the app it deploys exists.

**D7. Backlog phase 4 already carries the use cases and `composition.py`;
tightened, not added to.** Verified entry by entry — `AnalyzeScript`,
`ResolveFinding`, `AnswerProjectQuestion`, the Flask routes, `composition.py`,
and the OpenTelemetry setup are all present. What changed is that CP-005 froze
the five port signatures, so the phase-4 entries no longer have to defer on
"would guess at signatures": use cases depend on ports, not on adapters, and
those ports are now fixed. The Backlog preamble and the phase-4 entries are
rewritten to say what is now concrete and what genuinely still waits on the
adapters (only `composition.py`, which needs their constructors).

### Settled 2026-08-30, phase 4 planning (D8–D18)

Eight days to the 2026-09-07 submission. Every ruling below states what it
costs the demo, because that is the tiebreak now.

**D8. `python_version = "3.12"` is ratified; CP-012's archived criterion is
amended, not reverted.** CP-012 ticked a criterion pinning `"3.11"`;
`pyproject.toml` now reads `"3.12"` (conductor change, commit `959faf0`). The
cause is real and outside our code: `numpy` 2.5.2 is installed, it ships PEP 695
generic syntax in its stubs, a 3.11 mypy target cannot parse that syntax, and
`pytest` imports `numpy` under `TYPE_CHECKING`, so every test file drags it in.
The dev interpreter is 3.12.3. Reverting means suppressing numpy for mypy —
`follow_imports = skip` on a package we do not call — which trades a truthful
config line for a blind spot, to satisfy a criterion no longer describing the
toolchain. `requires-python` stays `>=3.11`: it is the floor for *running*
ClearCut, and nothing in `src/` uses 3.12-only syntax today.

The one edge this opens: mypy at 3.12 will accept syntax that a 3.11 runtime
rejects, and nothing catches it. That is closed by pinning the deployed runtime
rather than by another gate — the Cloud Run deploy checkpoint (Backlog) carries
`--runtime python312`, and CP-017 records the same in `pyproject.toml`'s
classifiers. CP-012's archived criterion gains a dated inline amendment; no new
checkpoint.

**D9. Confidence-to-risk: MEDIUM raises the risk one step, LOW sets
`needs_review` on the tracker item.** SDD §4.1 step 5 says low confidence "marks
the finding unverified", and `Finding` has no such field. Adding one means
changing a frozen, reviewed domain dataclass and every construction site, to
carry a producer-facing "do not trust this yet" signal that `TrackerItem` already
has a field for — `needs_review`, which D-day's delta path (§4.3) sets for
exactly the same reason. Reusing it keeps the domain unchanged, keeps one
vocabulary for one meaning in the dashboard, and costs nothing. So: HIGH leaves
the finding alone, MEDIUM calls `RiskLevel.raised()`, LOW leaves the risk and
sets `needs_review=True` on the item that finding produces. Owned by
`AnalyzeScript` (CP-025), never by an adapter, because `Confidence` carries no
risk rule of its own — `ports.py` says so in its own docstring.

**D10. `/api/analyze` takes a `gcs_uri` in this phase; multipart upload is a
later checkpoint with its own port.** The Backlog asked whether SDD §4.1 step 1's
"the route streams the PDF to `gs://...`" survives SDD §4's "routes do nothing
beyond mapping HTTP to use-case input and output". It does not: a GCS write is a
real I/O boundary, so it belongs behind a port with an adapter, not inside a
route. But SDD §4.1 already admits the other input — "multipart **or an existing
GCS URI**" — and taking only the URI removes a port, an adapter, and a
checkpoint from the critical path eight days out. The operator runs
`gcloud storage cp` and POSTs the URI; the intake bucket CP-013 provisions is
unchanged. Multipart upload with a `ScriptStorage` port is filed in the Backlog,
and it is the SPA's dependency, not the demo's.

**D11. The contradiction check earns its own narrow `ContinuityCheck` port. It
does not ride `SceneExtractor`.** The Backlog held this open; the frozen
signatures answer it. `SceneExtractor.extract(scenes, jurisdiction) ->
list[Finding]` cannot express "compare this scene against these facts": there is
no parameter for the facts. Riding it therefore means either changing a port
CP-005's review froze, or having the extractor adapter call `LoreStore` itself —
which puts orchestration inside an adapter and breaks AGENT.md §2 rule 3.

Is a second port proliferation, which §4 forbids? No: it is a second *network
call*, to a different model (gemini-3.1-flash-lite, SDD §4.1 step 5), with a
different prompt and a different output shape. §4 bans a port without a real I/O
boundary; this is one. It stays a single method — `check(scene, facts) ->
Finding | None` — which is narrower than the port it declined to join. It brings
the port count to eight, and it is the last one: nothing else in phase 4 or 5
crosses a boundary these eight do not already cover.

The one-line scene summary SDD §4.1 step 5 also attributes to flash-lite is
**not** in scope for that port. It is LoreStore row metadata, no use case reads
it, and no checkpoint needs it. Backlog.

**D12. `AnswerProjectQuestion` gets no ninth port.** SDD §3 fixes its
collaborators at `(lore, grounding, tracker)` and separately says it is "backed
by gemini-3.1-flash-lite". Taken literally that needs a fourth collaborator SDD
does not name. Resolved by observing what `LegalGrounding` already returns:
`GroundedAnswer(text, citations)` — Vertex AI Search's grounded natural-language
answer, cited. The use case retrieves bible facts through `LoreStore`, gets that
grounded text through `LegalGrounding` when the question names a legal topic,
reads tracker state for territory-blocker questions, and returns a
`ProjectAnswer` carrying all three with their citations. No free-text generation
in-process, so no port. The Agent Builder agent app CP-014 provisioned is where
conversational phrasing lives if the demo wants it, and it is already wired to
the same data store. If a later checkpoint proves prose composition is needed,
that is a new port with a real caller — which is the order §4 asks for.

**D13. `finding_id` is minted by `AnalyzeScript` as `EVT-NNN`, not by the
extractor.** Found while checking the phase-4 preconditions:
`adapters/gemini/extractor.py:141` sets `finding_id=str(uuid.uuid4())`, while
SDD §2 specifies `EVT-NNN`, "sequential per project, assigned at first detection
and **stable across script versions**". An adapter cannot produce that — it does
not know the project or its existing sequence, and a UUID is by construction not
stable across versions, which is precisely the identity EvaluateDelta's
carry-forward joins on. So the extractor's id is a placeholder the use case
replaces after dedupe. This is not a defect in CP-007: no criterion of its asked
for `EVT-NNN`, and the id had no consumer until now. Folded into CP-025 as a
criterion; no checkpoint against the adapter, which is left untouched.

**D14. OpenTelemetry is deferred to the Backlog, dated and reasoned.** SDD §6 and
§8(d) both name it, so this is a deliberate cut, not an oversight. Spans go
*inside* the adapters (§6: "Adapters create the spans around their outbound
calls"), so it is six diffs across five checkpoints that are `DONE` and reviewed,
plus a provider setup in `composition.py`, for a surface that changes no
user-facing behaviour. If it slips, the demo still runs; if the pipeline slips,
there is nothing to trace. It lands after the end-to-end run works, and the
Grafana dashboard §8(d) describes is the last thing built, not the first.
`composition.py` (CP-029) is therefore wiring only.

**D14 is OVERTURNED on 2026-08-30 by the user, relayed through the conductor.**
The original text above stays as written, because the triage was sound on its
own terms and a reader deserves to see why it was overridden rather than that it
vanished. Its costs were real: six diffs across reviewed checkpoints, a provider
setup, and no user-facing behaviour changed. What it did not weigh is that this
question was already closed. The user gave a standing instruction earlier in the
project — "grafana is not optional" — which is why SDD §6 specifies OTLP export
to Grafana Cloud and why `docs/plan/adr/observability/0008-observability-grafana-otel.md`
carries `Status: Accepted` with the words "a launch requirement rather than an
add-on". A leader may sequence a requirement a human has ruled on; it may not
triage the requirement away. The most D14 could legitimately do was put the cut
back to the user, which the conductor did, and the answer was to restore it as
an active checkpoint now.

The deciding argument is the debt, not the schedule. An accepted ADR that reads
"mandatory" over a repository that silently ignores it costs more than one
instrumentation cycle, because the next reader has no way to tell which of the
other nine ADRs are also dead letters, and the cheap way to find out is to
ignore all of them.

What changes: OpenTelemetry becomes CP-031 in Active, with the dependency edges
its real position in the graph gives it (CP-023, CP-029, CP-030) rather than a
place at the head of the queue — the user asked for it active, not for it to
jump the graph. What does not change: the Grafana dashboard and the check that
traces appear in it stay live checks under SDD §8, next to §8(a) through §8(d),
since none of them run in CI. CP-031's own acceptance criteria are verifiable
with no Grafana account at all.

(D14's last line names CP-029 for `composition.py`; that is CP-030. The original
sentence is left as it was.)

**D15. No checkpoint for the keyword-call-site guard D3's amendment leaves
open.** CP-009's reviewer offered two exits: strike "parameter names" from the
criterion, or open a checkpoint forcing one keyword call through each concrete
adapter so mypy sees a rename. Struck, for now. The exposure is a *future*
rename of a parameter on one of five adapters that are all `DONE`, frozen, and
touched by nothing on the phase-4 path; and the call sites that would break are
the use cases, which are being written this turn under one rule stated where
they are written: **use cases call port methods positionally**
(`self._grounding.ground(query, jurisdiction)`). That closes the gap at the only
five call sites that exist, at zero cost. Filed in the Backlog so a later turn
can add the guard when the file count makes a convention unreliable — which is
the same reasoning D4 used to reject a convention, applied honestly in the other
direction because there the file count was five *unseen* branches and here it is
five files one implementer writes.

**D16. `google-cloud-discoveryengine` 0.20.2 stays installed; CP-017 settles it
by making the `.venv` stop being the record.** CP-009's reviewer asked for it to
come out of the environment record. Uninstalling it from `.venv` is a local
mutation that no test observes, that a fresh `pip install` would undo, and that
risks breaking a transitive requirement of `langchain-google-vertexai` on the
one machine the demo is recorded from. The actual finding underneath it — that
`.venv` is the only record of what this project needs — is fixed by CP-017,
which declares the dependencies in `pyproject.toml` and adds a test that fails
when `src/` imports something undeclared. Once that lands, an extra package in
`.venv` is noise, not a record. No separate checkpoint; do **not** uninstall.

**D17. `infra/README.md`'s missing "upload the PDFs first" step is folded into
the Cloud Run deploy checkpoint, in the Backlog.** CP-014's run order jumps from
step 3 to `gcloud storage ls "gs://clearcut-legal-corpus/**"` without ever
saying a human must put the legal PDFs in that bucket first. Real, and worth
fixing — but it fails loudly (an empty listing yields an empty manifest, and
CP-014's own failure path exits non-zero before creating an empty data store),
so nobody is misled, they are stopped. Two lines of prose do not earn an
implementer turn plus a reviewer turn eight days out. The Cloud Run deploy
checkpoint edits the same run-order list in the same file; it carries this as a
criterion so it cannot be lost.

**D18. The two `web/` findings wait for the container that makes them bite.**
(a) Malformed JSON inside a 200 escapes `requestJson` as a raw `SyntaxError`
rather than `ApiError` (`web/src/api/client.ts:108`). Real, and confirmed by
CP-011's reviewer with a probe — but the only backend that will ever answer this
client is Flask's `jsonify`, which does not emit malformed JSON, and the code
that would miss the distinction (a container branching on `instanceof ApiError`)
does not exist yet. It is one `try/catch` and one test, and it belongs in the
checkpoint that writes that branch. (b) Tailwind, which ADR 0009 and SDD §5 name
as stack and CP-011 correctly declined to add with nothing testing it, lands
with the first container that needs visual styling. Both are attached to the
first-container Backlog entry rather than left implicit.

### Settled 2026-08-30, the specification queue two reviews left open (D19–D21)

Four questions arrived from reviewers with evidence attached. None blocks a
checkpoint today, and every one of them decides itself the wrong way if nobody
rules — which is the only reason they are worth a leader turn eight days out.

**D19. Scene renumbering is accepted as full re-analysis cost. ADR 0007's
Consequences paragraph is amended; SDD §2, `diff_scenes`, and CP-020's criteria
are not.** CP-020's reviewer established the conflict precisely: SDD §2 states
the `(number, heading)` join normatively twice, CP-020's criteria restate it
four times, and criterion 5 declares REMOVED+ADDED the *correct* answer for a
same-number heading change. So a hash-first join is not a refinement of the
spec, it is a different spec.

What the ADR asks for splits in two, and only one half is unserved.
*Correctness holds.* Permissions are not lost on renumbering: carry-forward
joins on asset identity — `(category, normalized raw_text)`, SDD §4.3 and
CP-028's own criterion — "even when the asset moved to a different scene", and
REMOVED scenes keep their open tracker items. `content_hash` is position-free
and verified so. The ADR's Decision paragraph is satisfied in full. *Compute is
wasted.* Top-inserting one scene renumbers every scene below it, and a
`(number, heading)` join never pairs them, so each is re-extracted and
re-embedded although its text is identical.

Ruling for the second half rather than against it, on four grounds:

- **The demo does not exercise it.** SDD §7 phase 5's exit condition is
  "uploading v2 with **one edited scene** re-analyzes exactly that scene and
  preserves CLEARED items". An edited scene keeps its number and its heading,
  so the key join pairs it and the hash comparison decides it. The demo beat
  lands under the join as built.
- **Hash-first is incomplete, not merely costly.** It rescues only the
  renumbered-*and*-unchanged scene. A scene both renumbered and edited misses
  the hash join and then misses the key join too, so it still reads
  REMOVED+ADDED.
- **It needs a tie-break nothing specifies.** `content_hash` is not unique
  within a version — two short scenes with identical normalized text collide —
  and `diff_scenes` currently raises `ValueError` on a duplicate key. Inventing
  a collision policy now, for a function whose only consumer (CP-028) is
  unwritten, is the speculative generality §4 forbids.
- **The costs are asymmetric.** Amending the ADR is one paragraph. The other
  road reopens a reviewed `DONE` domain module, rewrites two SDD §2 sentences
  and two CP-020 criteria, and spends a review, to change behaviour no
  checkpoint calls yet.

The counterweight, recorded because it cuts against this ruling rather than for
it: `Scene.number` is an `int`, so ClearCut cannot represent the `14A` insert
that production practice uses on a locked script precisely to avoid renumbering
everything downstream. The waste is therefore not purely theoretical for a real
series. That is a modelling gap in the scene number, not in the join key, and it
is filed in the Backlog as one. It does not change today's answer, because the
fix for it is a different change.

Amendment text for
`docs/plan/adr/architecture/0007-incremental-delta-by-scene-hash.md`, replacing
its Consequences section entirely. It is carried as a criterion on CP-028,
whose behaviour the paragraph describes, on D17's precedent: one paragraph does
not earn an implementer turn plus a reviewer turn, and the checkpoint that pays
the cost is the one whose reader needs the ADR to be true.

> ## Consequences
>
> Scenes hash on content rather than position: `content_hash` covers the
> normalized text and nothing else, so a renumbered but unchanged scene
> produces the same hash.
>
> The join key is a separate question, and SDD §2 answers it differently:
> scenes join across versions on `number` plus `heading`. Renumbering a scene
> therefore does not merely move it, it changes its identity — the old number
> leaves as REMOVED, the new one arrives as ADDED, and the two equal hashes are
> never compared. Inserting a scene re-analyzes every scene below it.
>
> That cost is accepted. Clearance does not depend on it: carry-forward joins
> on asset identity, `(category, normalized raw_text)`, not on the scene, so a
> renumbered scene's findings keep their `finding_id` and their tracker state,
> and REMOVED scenes keep their open items. What is spent is compute. Joining
> on the hash first would recover some of it, but only for scenes renumbered
> and left otherwise untouched, and it would need a rule for two scenes in one
> version that hash alike — `content_hash` is not unique within a version.
> Neither piece is specified, so neither is built.
>
> Edits below scene granularity also cost full price; a single changed line
> re-embeds and re-analyzes the whole scene.

**D19 corrected on 2026-08-31 by D37. The original text above stands unedited;
this paragraph is the correction.** The "*Correctness holds*" half of this
ruling rested on a behaviour that does not exist. It quoted CP-028's criterion
5 — "carry-forward joins on asset identity — `(category, normalized raw_text)`"
— and CP-028's review then measured that nothing in this repository can join on
that pair: `TrackerItem` carries no `category` and no `raw_text`, `TrackerStore`
exposes no findings read, and `infrastructure.md` §6 defines no findings table.
Carry-forward joins on scene overlap. So permissions survive only for a scene
that keeps its number, which is the case SDD §7 phase 5 demonstrates and the
only case the demo exercises. An asset that moves to a different scene arrives
as a new item at BLOCKED and a human clears it a second time, while the item it
left behind stays open and flagged.

The ruling stands, on the three grounds that never depended on the false
premise: the demo does not exercise renumbering, hash-first is incomplete
rather than merely costly, and it needs a tie-break nothing specifies. What
changes is the size of the cost being accepted. It is not compute alone. The
amendment text above is superseded by D37's, which says so in the ADR, and
CP-045 lands it.

**D20. `scene_numbers` is the set of scenes an asset appears in, not a list of
its mentions. CP-032 makes it one.** CP-019's reviewer verified against the
built module that `dedupe_findings([f("E1", 7), f("E2", 7), f("E3", 9)])`
returns `(7, 7, 9)`, and correctly called it unspecified rather than a defect —
no criterion and no contract forbids it, and `TrackerItem` rejects only an
empty tuple.

Accepting multiplicity would mean deciding what a repeat *means* to a producer
reading the tracker, and no answer survives contact with the identity function.
It cannot mean "mentioned twice in scene 7", because dedupe collapses on
`(category, normalized raw_text)`: two mentions of the same asset in scene 7
whose text differs at all stay separate entries and never meet. So a repeat
counts only mentions whose normalized text matches exactly, which is a statistic
about the screenwriter's phrasing rather than about clearance. Nothing reads it,
no criterion asks for it, and SDD §2 calls the field "every scene where the
asset appears" — a set, in the only reading that makes the sentence true.

This clears the test I apply to every deferred finding: it changes observable
behaviour. CP-023 persists the tuple and the dashboard renders it, so left alone
it reaches the producer as "scenes 7, 7 and 9". The change is one line and a
test, inside a pure domain function with no I/O — CP-032.

**D21. The dependency gate resolves imports by dotted path. CP-017's second
acceptance criterion is amended and CP-033 closes it; the repeated failure
output rides along.** CP-017's reviewer measured the gate twice and got the same
number both times: it catches 2 of 6 single removals, and declaring
`google-api-core` by hand closed one instance without extending what the gate
can see. `packages_distributions()` resolves whole top-level names only, so all
seventeen `google-*` distributions collapse onto one key and declaring any one
of them satisfies an import of any other. Closing that needs
`Distribution.files` prefix matching, which the reviewer ran and confirmed
resolves all five imports correctly — and which the second acceptance criterion
forbids by naming the stdlib call. That is a specification change, so it is
mine.

A dated acceptance was the other exit, and the expected one, because the same
reviewer proved no second undeclared import is hiding today. What overturns it is
CP-031. `opentelemetry-api`, `opentelemetry-sdk`, and
`opentelemetry-exporter-otlp-proto-http` all install under a single
`opentelemetry` top-level namespace, the same shape as `google`, so under
today's checker declaring one of the three satisfies imports of all three. The
failure mode is specific and bad: `gcloud run deploy --source .` ships a
container missing the exporter, every local test stays green, and the service
dies at import on the one deploy the submission depends on. Declaring all three
by hand is available, and it is exactly the remembering CP-017 exists to remove
— its own Notes say so: "a list somebody has to remember to update is exactly
what let `dependencies = []` survive five adapters."

Neither pending import needs this on its own. `clickhouse-connect` (CP-023) and
`flask` (CP-029) each own their top-level name, and an import of a distribution
that is not installed at all is already reported rather than skipped — verified
against the checker: an empty candidate set fails the intersection and the
finding prints `<none installed>`. That behaviour is load-bearing for all three
of those checkpoints, so CP-033 pins it with a test rather than leaving a
rewrite free to drop it.

CP-017's item (b) — the failure output repeating one finding per import
statement, seven times over for `parallel-web` — folds into CP-033 rather than
into the Backlog or a turn of its own. Same file, same function, one grouping,
and it is the half of the output a human actually reads.

### Settled 2026-08-30, six questions from four reviewers (D22–D26)

Every one of them lands on a checkpoint that has not been dispatched — CP-025,
CP-026, CP-029, CP-030 — which is the whole reason they are worth a turn today.
Two of them (D23, D24) decide code three unwritten use cases are about to
contain; ruling those after the code exists costs three reopened modules
instead of one new checkpoint. Four checkpoints come out of these five
rulings: CP-034 through CP-037.

**D22. `TrackerItem` gains `with_draft_email(text, at)`, and CP-025's `Files`
widen to reach it.** CP-018's reviewer found the mismatch: CP-025 must store a
draft on an item, `TrackerItem` exposes only `transitioned_to` and
`flagged_for_review`, and CP-025's `Files` exclude `domain/tracker.py`. As
written that use case reaches for `dataclasses.replace` and bumps `version`
itself, which hands the versioned-row rule — every change is a new row at
`version + 1`, never a mutation (SDD §2) — a second owner in a second layer.

Ruled the first way the reviewer offered. `with_draft_email(text, at)` is a
third sibling of two methods that already exist, returning a new item at
`version + 1` with `state` unchanged, in the exact shape `flagged_for_review`
already has. It is not a new abstraction under §4: it is one more
`dataclasses.replace` one-liner on the aggregate that owns the other two, which
is Information Expert applied where §3 says to apply it.

Sanctioning `replace` in the use case costs the same number of lines and buys a
second place that knows how a version is bumped. The day that rule gains a
field — an `updated_by`, say — one of the two sites gets missed, and
ClickHouse's latest-wins read resolves the miss to a stale row with nothing to
signal it. That is the same failure CP-018's own `frozen=True` test exists to
catch, which is the evidence that this project already decided this question
once in the other direction.

CP-025 also gains a criterion that its module contains no `dataclasses.replace`
on a `TrackerItem`. It is a one-line source assertion in that use case's own
test file, not a guard framework — but "the use case does not bump versions" is
a convention until something fails without it, and conventions are what D4
already declined to trust.

**D23. Adapter errors cross the port as domain errors, by subclassing three
types in `domain/errors.py`. CP-034 does it; CP-035 carries the transport
half.** CP-027's reviewer measured the cost of today's arrangement rather than
asserting it: `src/clearcut/application/answer_project_question.py:109-111`
holds the repo's first and only `except` in `application/`, it is
`except Exception`, and injecting `TypeError`, `AttributeError` and
`ZeroDivisionError` into `grounding.ground` each produced a silent bible-only
answer. `KeyboardInterrupt` correctly propagates, since the catch is
`Exception` and not `BaseException`.

The implementer had no other legal move. `NoGroundedSource` lives at
`adapters/gcp/vertex_search.py:27`, `application/` may not import
`clearcut.adapters` (`tests/unit/test_layer_boundaries.py` enforces it), so
that layer had no name to catch. CP-006's ruling — all five verticals keep
their errors in their own module, `domain/errors.py` holds only
`UnknownJurisdiction` — answered *where the class is defined*, at a time when
nothing outside `adapters/` ever caught one. It never answered how a caller
names one, and it is being extended into that gap by one implementer at a time.

What decides this is not the swallowed `TypeError`, real as that is. It is
CP-029 and CP-030 read together. CP-029 must map "the adapter's not-found error
to 404 and an adapter unavailability error to 502". Its module is
`src/clearcut/adapters/http/routes.py`, so under today's convention it names
those errors by importing `clearcut.adapters.clickhouse.tracker` — and CP-030's
second criterion makes `composition.py` "the only module under
`src/clearcut/` importing from `clearcut.adapters`", enforced by extending the
layer-boundary test. **The two checkpoints cannot both pass as written.** One of
them would have been quietly rewritten mid-turn by whichever implementer hit it
first, which is the outcome this decision exists to prevent.

The ruling: `domain/errors.py` gains three types, and every adapter error
subclasses exactly one of them.

- `RecordNotFound` — the record asked for does not exist. CP-029 maps it to
  404. Subclass: `TrackerItemNotFound`.
- `SourceUnavailable` — an external source could not answer and the request
  cannot continue without it. CP-029 maps it to 502. Subclasses:
  `TrackerUnavailable`, `LoreUnavailable`, `IngestionFailed`, `NoScenesFound`,
  `ExtractionFailed`, `ResearchUnavailable`, `ContinuityCheckFailed`,
  `NotificationFailed`.
- `EnrichmentMissing` — a source answered and had nothing to add for this
  input. The caller continues without it, and it never reaches a route.
  Subclasses: `NoGroundedSource`, `NoRightsHolderFound`.

*Subclassing, not replacing.* That is what makes this cheap, and it is also
what keeps CP-006's ruling true instead of overturning it. The class stays in
its adapter module and keeps naming the processor id or the item id — "an error
naming a processor id is an adapter's translation, not a domain rule" is still
right. What changes is the *type* that crosses the port, which becomes a domain
type, which is what §2 rule 3 has asked for since before CP-006 was written.
Each `src/` edit is one word inside one class statement.

*Three names, not one and not eight.* Each has a caller named in an existing
checkpoint's criteria today: `RecordNotFound` in CP-029's 404 line and CP-025's
propagate-unchanged failure path; `SourceUnavailable` in CP-029's 502 line;
`EnrichmentMissing` in CP-026's "one enrichment failure does not fail the run"
and in CP-027's repaired catch. A fourth would have none, which is exactly what
§4 forbids.

*The one imprecision, recorded rather than smoothed over.* `NoScenesFound`
means a PDF parsed and held no scenes — bad input, not a broken upstream — and
502 mislabels it. A fourth class for it would have no caller, because no
checkpoint asks for a 422. It goes under `SourceUnavailable` and earns its own
class the day a checkpoint needs the distinction.

*Where the fatal line falls.* `ResearchUnavailable` is a Parallel API 5xx, not
an unresolvable holder, so it is fatal and sits under `SourceUnavailable`.
CP-026 names only `NoGroundedSource` and `NoRightsHolderFound` as survivable,
and that is the right split: a Parallel outage that quietly yields a report
with no rights holder on any finding is worse for a demo than a 502 that says
what happened.

CP-034 carries all of it — the three types, the eleven class statements, the
repair of `answer_project_question.py` to `except EnrichmentMissing`, one
contract test that fails on a twelfth unclassified adapter error, and one guard
that fails on a bare `except Exception` under `application/`. Its dependencies
on CP-016, CP-022 and CP-036 are file disjointness only.

*The transport half, and why it is a separate checkpoint.* CP-024's reviewer
found `httpx.ConnectError` and `httpx.ReadTimeout` leaving `webhook.py:34` raw,
and `research.py:96` has the same shape, catching only `APIStatusError`. A
caller handling a refused connection would `import httpx` in `application/`,
which §2 rule 2 forbids. Same rule, different work: those two adapters wrap
their outbound call so `httpx.TransportError` — the common base of both — turns
into the adapter's own error under `SourceUnavailable`. It is two `except`
clauses and their tests, it is a distinct behaviour from classifying errors
that already exist, and unlike CP-034 it is cuttable: a refused connection
during the demo is an infrastructure failure a 500 also reports, whereas CP-029
cannot be written at all until CP-034 lands. CP-035.

**D24. `TrackerItem` gains `project_id`. `ports.py` is not touched at all, and
CP-036 lands it before CP-025 and CP-026 write their call sites.** CP-023's
reviewer verified the gap against the built code and it is exactly as reported:
`domain/tracker.py` gives `TrackerItem` no `project_id`, `ports.py` declares
`save(items: list[TrackerItem]) -> None` with no project channel, and
`adapters/clickhouse/tracker.py:150-151` issues `SELECT * FROM tracker_items`
with no `WHERE`, ignoring the `project_id` it was handed. `latest_for_project`
returns the latest version of every item in the table. The asymmetry is visible
one method away: `latest_script(project_id)` does filter, at `tracker.py:173`,
because `Script` carries `project_id` and `TrackerItem` does not.

Both exits the reviewer offered are declined, and a third is taken.

*Why not accept single-project scope.* No demo path exercises it — SDD §8(d)
seeds one project, and with one project's rows in the table the unfiltered read
returns the right answer, so accepting it costs nothing before 2026-09-07. What
decides against it is that three unwritten use cases are about to be written
against a read method whose parameter is decorative. A parameter that is
ignored gets copied, and the next reader reasonably assumes rows are
project-scoped because the method's name says so.

*Why not `save(project_id, items)`, which is what the reviewer proposed.*
It breaks `ResolveFinding`. CP-025 loads one item by `item_id`, changes it, and
saves the new version; SDD §4.2's routes for it are `PATCH /api/tracker/
{item_id}` and `POST /api/tracker/{item_id}/actions`, both item-scoped. Under
that signature the use case must be handed a `project_id` it has no way to
know, so the fix propagates into `execute`'s parameters, into two route bodies,
and into the SPA client that fills them — to write a column it could have read
off the item it just loaded.

*Why the field.* `LoreStore.index(project_id, records)` carries scope
separately, and that is correct there for a reason that does not transfer:
`BibleFact` and `Scene` are only ever written by `AnalyzeScript` and
`EvaluateDelta`, and both hold the project. `TrackerItem` is written by those
two *and* by `ResolveFinding`, which does not. A type written from an
item-scoped context has to be self-describing. So the project goes on the item,
`save(items)` is unchanged, and `latest_for_project` filters on the column
`save` now writes.

The consequence worth stating plainly: **no port signature changes.** `ports.py`
is not opened, so none of the eight checkpoints built on it is disturbed, and
CP-036 takes no dependency on CP-022's in-flight `ports.py` edit.

*The cost, measured not guessed.* `TrackerItem` goes to thirteen fields where
SDD §2 lists twelve; that deviation is recorded here rather than hidden, and it
is the same kind of call D13 made about `finding_id`. There are eight
`TrackerItem(` construction sites in five files, all of them factories in test
modules plus `_row_to_tracker_item` in the ClickHouse adapter, so the mechanical
cost is one non-default field and eight call sites. Doing this after CP-025,
CP-026 and CP-028 land adds three application modules, their tests, and the D15
positional-call tests that pin how each of them calls `save`. This is the
cheapest this fix will ever be, and it gets monotonically more expensive from
here — which is the whole argument for spending a turn on it now.

CP-036 carries it, depending on CP-023 and CP-024 for file disjointness.
CP-025, CP-026 and CP-034 depend on it.

**D25. `_LEGAL_TOPIC_WORDS` is widened, including past morphology. CP-037.**
CP-027's reviewer measured the vocabulary against the document it implements.
`docs/plan/agentic-workflow.md` §6's own canonical example — "Can we show the
mural in scene 12?", the question that section says pulls grounded Mexican law
— returns `False`. So do "Do we need permission for the Coca-Cola bottle?"
("permit" is listed, "permission" is not) and "Is the song cleared for
streaming?" ("clearance" is, "cleared" is not). Every miss degrades safely to a
bible-only answer and no criterion pins the vocabulary, which is why it is
scope and not a defect.

Widened, because the failure lands on a demo beat. Two of the three misses are
morphology — `permit`/`permission`, `clearance`/`cleared`,
`license`/`licensed` — and stem prefixes close them. The third is not: "Can we
show the mural in scene 12?" contains no legal word at all, in any form. It is
a clearance question because of what it proposes to *do* with an asset, so the
vocabulary has to reach the depiction verbs — `show`, `use`, `depict`,
`feature`, `display` — before the plan's own example works.

That widening buys false positives; "show me the blocked items" would ground.
The false positive is the cheap error, at one Vertex AI Search call. The false
negative costs the Q&A beat outright: the canonical question answered from the
bible alone, no Mexican law, no citation, in front of whoever is watching.
CP-027's zero-call criterion stays satisfied — it asks that a question naming no
legal topic calls `ground` zero times, and that stays true for the questions it
names.

Ceiling under §4: a frozenset of stems and `str.startswith`. No stemmer, no NLP
dependency, no model call inside a predicate. If stems stop being enough, the
answer is a different retrieval trigger with a per-call cost attached, which is
what the reviewer said, and that is a different checkpoint.

**D26. `TrackerItem` gets no jurisdiction field. Declined; the answer stops
implying the filter instead.** `docs/plan/agentic-workflow.md` §6 describes
"What is still blocking release in Mexico?" as a query for "BLOCKED items whose
jurisdiction set includes Mexico". `TrackerItem` carries no jurisdiction, so
the answer lists every blocked item in the project.

Declined, and unlike D24 this one does not get more expensive by waiting — it
gets cheaper. A per-item jurisdiction *set* only means something once one
project is analyzed against several jurisdictions, and nothing builds that:
`SceneExtractor.extract(scenes, jurisdiction)` takes one,
`LegalGrounding.ground(query, jurisdiction)` takes one, `AnalyzeScript` runs
against one, and CP-029's `POST /api/analyze` accepts one `jurisdiction_code`.
Every item a run produces therefore shares that run's single jurisdiction, so
today's unfiltered answer is *correct* for the demo rather than merely
harmless. The field's shape depends on a feature that does not exist, and
guessing it now is the speculative generality §4 forbids. SDD §2 does not list
it among `TrackerItem`'s fields either.

The cost of building it anyway: a field on a domain dataclass CP-018 reviewed,
a ClickHouse column, construction sites in CP-025 and CP-026, and a filter in
the Q&A use case — four checkpoints for a filter with exactly one correct
input.

What is fixed instead, because a decline should not leave a misleading answer
standing: the blocker answer names the jurisdiction it covers.
`AnswerProjectQuestion.execute(project_id, question, jurisdiction)` already
receives one, so the text can state which territory these items are blocked in
rather than implying a filter `TrackerItem` cannot express. One line and one
test, carried by CP-037 because it is the same file. The field itself goes to
the Backlog, behind the multi-jurisdiction analysis it needs.

**D27. The bare `ValueError`s stay where they are. The one that a request can
actually reach is stopped at the route, by widening a criterion CP-029 already
has; the other is unreachable and a 500 is the honest answer. No fourth error
class.** CP-034's reviewer is right that `vertex_search.py:58` and
`lore_store.py:93` cross a port as non-domain types and that CP-034's contract
walk cannot see them — it collects module-owned `Exception` subclasses, and a
`raise ValueError` is neither. What the report does not separate, and what
decides this, is that the two are not reachable the same way.

*Three sites, not two, and the third is already owned.* `webhook.py:30` raises
the same bare `ValueError` on a blank `webhook_url`. It is in `__init__`, not in
a port method, so it fires in `composition.py` at startup — which is exactly
CP-030's "a missing required variable fails at startup naming that variable, not
at the first request". Nothing to do; recorded so the next reader who greps
`raise ValueError` under `adapters/` finds all three ruled.

*`vertex_search.py:58` cannot be reached from any request.* A `Jurisdiction` is
never constructed from request data: `jurisdiction_for` (`domain/jurisdiction.py:38`)
returns one of the ten frozen values in `JURISDICTIONS` or raises
`UnknownJurisdiction`, and all ten carry a non-blank `corpus_prefix`. A blank
prefix therefore means someone edited that tuple, which is a programming error,
and a 500 is what a programming error should be. The guard is not deleted
either: `jurisdiction: ANY("")` returns every jurisdiction rather than failing,
so removing it trades a loud 500 for silently unfiltered legal citations — the
failure D2 named when it put this guard here.

*`lore_store.py:93` is reachable, and it is a bad request, not a bug.*
`POST /api/question` carries `project_id` from the body into
`AnswerProjectQuestion.execute`, which passes it straight to
`self._lore.search(project_id, ...)` (`answer_project_question.py:99`). A blank
one lands on that guard and leaves as a bare `ValueError`, so today it would be
a 500 for input the caller got wrong. That is a route's job, and CP-029 already
does it for one field: "`POST /api/analyze` without `gcs_uri` returns 400 naming
the missing field, before any adapter call". The criterion is widened from one
field to the rule it was already an instance of, covering the two routes that
take a `project_id`. The adapter guard then becomes what the other one already
is — unreachable from a request, and a 500 if it ever fires.

*Why not a fourth base under `domain/errors.py` mapping to 400.* D23's rule was
that each of the three names has a caller in some checkpoint's criteria today,
and that a fourth would have none. That still holds after this ruling and
because of it: once the route refuses a blank field, no reachable raiser is left
to classify. Building the class anyway is an interface with one implementation
and no caller, which §4 bans by name, and it would have to reclassify raise
sites CP-034's last criterion deliberately froze.

*The blind spot, recorded rather than closed.* The contract walk will never see
a `raise ValueError`, and no widening of it would — catching that shape needs a
raise-site AST scan, a third structural guard, for a rule with three known sites
that are now all ruled. It goes to the Backlog with this reason. What lands
instead is a behavioural pin at the only place it can be observed: CP-029's 500
criterion gains a `ValueError` case, so if either guard ever does fire, the
response is a 500 with a JSON body and no stack trace rather than a Flask
traceback in front of whoever is watching the demo. Two amended criteria on
CP-029, no new checkpoint, no `src/` change.

**D28. `NotificationFailed` reaching a 502 is correct on the path that exists.
Declined, because the partial success it would misreport does not happen — and
the trigger that reopens this is named.** Verified against `resolve_finding.py`
rather than against the report, because the report's premise is checkable and it
does not hold. `ResolveFinding.execute` (`resolve_finding.py:74-80`) reads
`self._tracker.latest(item_id)`, and on a `Notify` action calls
`self._notifier.notify(...)` and returns the item **unchanged**. The `save` is in
the other branch, after `_apply`. No path in that module both writes a row and
notifies, and `rg` confirms `notify` has exactly one call site in `src/`.

So the request the reviewer describes — the producer clicks approve, the row is
written, the UI is told it failed — is not a request this code can serve.
`POST /api/tracker/{item_id}/actions` with `{"action": "notify"}` writes nothing;
notifying *is* the whole request. When it fails, 502 says the one thing that
happened, and it is true. The transition paths (`PATCH /api/tracker/{item_id}`,
and `actions` with `draft_email`) write and never notify, so their only 502 comes
from `TrackerUnavailable`, which is a write that genuinely failed.

*Neither exit is taken, and that is the point.* `ResolveFinding` does not catch:
a catch would swallow the only failure a notify request has to report, turning a
502 into a 200 that lies — the same swallowing D23 spent a checkpoint removing
from `answer_project_question.py`. The route does not distinguish either, because
there are not two outcomes to tell apart. `NotificationFailed`'s place under
`SourceUnavailable` (D23, CP-034) is unaffected by this ruling in either
direction; the type was never the question.

*What reopens it, written down so the next turn decides on evidence.* The day one
action both writes a row and notifies, the write becomes observable and 502
becomes wrong. The two likeliest are the Backlog's `generate_document` and
`stakeholder_link`, or a transition that notifies on entering BLOCKED. The fix
then is not a status code and not a catch in the use case: it is to report the
outcome of the write and carry the notification failure as a field in the
response body, which SDD §4.1 step 8's JSON shape already accommodates. Building
that today means a catch with no failure it can honestly report and a
partial-success shape on a route that has no partial success — speculative
generality under §4, eight days out. CP-029 needs no criterion for it; the note
on that block records it so the implementer does not re-derive it mid-turn.

**D29. Both guards in `test_error_boundaries.py` are widened. CP-038, and it is
dispatchable today.** These two are the ones that cost nothing to accept and
buy back the thing CP-034 was careful about: a guard that cannot fail is worse
than no guard, because the suite reports it as green.

*The AST guard is narrower than its own purpose.* It matches `ast.Name` with id
`"Exception"` only (`test_error_boundaries.py:62-64`), so `except:` — where
`node.type` is `None` — and `except (Exception,)` — an `ast.Tuple` — both pass,
proven by mutation, not read off. The guard exists so `application/` names what
it catches, and two of the three ways to not name it are invisible to it.
CP-025's `resolve_finding.py` has no behavioural backstop of its own, so this is
the only thing standing between a future `except:` and exactly the swallowing
D23 measured. `except BaseException` rides along in the same predicate for the
same reason and the same cost.

*The contract walk can pass vacuously.* `pkgutil.walk_packages` with no
`onerror` swallows an `ImportError` and drops that module from the walk, so an
adapter that fails to import is an adapter the test never inspected, and it goes
green. This is the same failure class as the `parents[1]` bug CP-034's
implementer caught by mutation — a guard that always passes — and it matters now
rather than later because CP-029 is about to add the first new adapter package
since the walk was written.

*One checkpoint, not two, and not folded into CP-029.* Both are edits to one
file that nothing else opens: CP-034 deliberately kept these guards out of
`test_layer_boundaries.py`, which CP-030, CP-031 and CP-035 all extend. Neither
touches `src/`, both are gate integrity rather than behaviour, and folding them
into CP-029 would put a tests-only fix behind CP-026 for no reason. CP-038 is
dependency-free and parallel-safe with everything in flight.

*The one constraint on how it is built.* The non-vacuity assertion is
membership-based, never a module count: CP-029 adds `adapters/http/`, and a
count would turn red for the wrong reason in someone else's turn. And the
widened AST predicate must still pass on the narrow catches CP-034 installed,
including a tuple of two domain errors — a guard that bans the fix it was
written to protect is not a stricter guard, it is a broken one. Both are
criteria on the block.

### Settled 2026-08-30, six findings from four reviewers (D30–D35)

All six arrived non-blocking, from checkpoints that have since passed. Two of
them — D30 and D31 — are not about how ClearCut is built but about what it
claims to do, and both would ship silently: one leaves a headline feature with
no data to run on, the other answers a clearance question with an assurance it
has no evidence for. That is why they get checkpoints eight days out rather
than Backlog lines. Four checkpoints come out of the six: CP-039 through
CP-042.

**D30. `AnalyzeScript` calls `record_script` after `tracker.save`, and
`EvaluateDelta` does the same for the version it produces. The route cannot,
and `POST /api/analyze` carries the version so it does not have to. CP-039
lands the writer, CP-041 lands the caller `EvaluateDelta` would otherwise never
get.** CP-026's reviewer verified it twice: `record_script` is declared at
`ports.py:115`, implemented at `adapters/clickhouse/tracker.py:165`, and called
from no module under `src/`. So `latest_script` has no writer, CP-028's first
step diffs against `None` forever, and incremental delta evaluation — a
headline feature in `docs/plan/proposal.md` and one of the five demo beats —
cannot run even once. CP-026 was right to leave it out: no criterion of its
named the call, and its ordered-sequence test ends at `tracker.save`, so an
unrequested call would have failed that assertion as readily as satisfied
anything.

*Not the route, on three grounds.* CP-029's factory takes use-case instances
and nothing else, so a route that wrote the script row would have to hold a
`TrackerStore` — which SDD §4 forbids in the same sentence that defines the
layer ("routes do nothing beyond mapping HTTP to use-case input and output"),
and which CP-030's import gate would then have to be argued down. The use case
already holds that port and already builds the `Script`
(`analyze_script.py:142-149`), so Information Expert (§3) puts the write where
the data is. And the write has to happen on both paths — first analysis and
every re-analysis — so a route-side write would be the same three lines in two
places, one of which a later checkpoint forgets.

*After `save`, not before.* Then `latest_script` only ever names a version
whose tracker items are persisted. A script row recorded ahead of a failing
save advertises an analysis that never landed, and the next upload diffs
against it.

*The other half of the same defect is the caller.* After CP-028,
`EvaluateDelta` has no route either, and a use case nothing calls is the same
kind of gap as a port method nothing writes. SDD §4.3's first sentence says
what its edge is: "Triggered when `POST /api/analyze` receives a project that
already has a script version." Deciding that inside the route needs a tracker
read the route may not do. The version comes from the request instead — which
it has to anyway, because `AnalyzeScript.execute` takes `version: int`
(`analyze_script.py:132-140`) and CP-029's three-field body has no way to
supply it. `version == 1` calls `AnalyzeScript`, `version > 1` calls
`EvaluateDelta`: one comparison, no read, no new port. D10 already set this
precedent — the operator supplies the `gcs_uri` the system would otherwise
derive, and supplying the version number is the same class of input. The cost
is recorded rather than hidden: a caller that posts `version: 1` twice
re-analyzes from scratch and records v1 again. Harmless for a two-version demo,
and the honest fix is a project store, which the Backlog already holds.

*Why CP-041 rather than a sixth route inside CP-029.* The branch needs
`EvaluateDelta` to exist, so folding it in makes the largest route checkpoint
wait on the largest use case, and CP-030 and CP-031 queue behind both. As its
own node it is one comparison and its tests, it lands before CP-030 so
`composition.py` is wired once, and CP-029 — which the conductor is dispatching
now — keeps its dependency set of four `DONE` checkpoints.

*No fourth error class.* CP-028's "no stored previous version" error subclasses
`RecordNotFound` from `clearcut.domain.errors`, so CP-029's existing 404
mapping covers it unchanged. D23's rule holds — the name already has callers —
and D27's does too: nothing new to classify.

**D31. A blocker answer over an empty tracker says the project is not indexed.
It does not say nothing is blocked. CP-040.** CP-037's reviewer measured the
regression its own criterion asked for: a blocker question against a project
with zero tracker rows now answers "Nothing is blocked in Mexico.", where
before CP-037 it answered "I have nothing indexed for this project." The
reviewer passed the checkpoint correctly — the criterion asked for that
phrasing, and nothing calls `AnswerProjectQuestion` yet, so no caller observes
it.

It is worth a checkpoint because the two sentences are the two halves of the
liability argument this product is built on. `docs/plan/proposal.md` sells
clearance evidence: a producer who reads "nothing is blocked" and ships is
relying on a search that ran, and a producer who reads "nothing is indexed"
knows to go and index. An empty dataset produces the first sentence today, so
the assurance is derived from absence of data — which is the one input that
cannot support it. Every other finding in this batch costs money, a call, or a
reader's understanding; this one costs a claim the product cannot back.

Three cases, one rule — **assurance requires rows**:

1. no tracker rows for the project → nothing is indexed for it, and the text
   makes no clearance claim at all;
2. rows exist, none BLOCKED → nothing is blocked in the territory `execute` was
   given, named (D26's line, kept);
3. rows exist, some BLOCKED → unchanged.

*Not CP-029.* The sentence is composed in
`application/answer_project_question.py`, and a route that reworded it would be
holding a rule the use case owns. CP-040 is that one file, one behaviour, and
dispatchable today in parallel with CP-029. It narrows CP-037's sixth
criterion — "the territory is named even when nothing is blocked" now holds for
case 2 and not for case 1 — which is recorded here and pointed at from CP-037's
archived Notes, on D8's precedent for amending a criterion that has already
passed.

**D32. `LegalGrounding` skips CONTINUITY and POLICY, on the argument CP-026
already accepted for `RightsResearch`. CP-039, with the SDD sentence that
describes it.** CP-026's reviewer found `_citations_for` unconditional at
`analyze_script.py:183` while only `_claim_for` consults
`_NO_RESEARCH_CATEGORIES`, so the legal corpus is queried with strings like
`"CONTINUITY clearance: The mural was already destroyed in scene 3."`

The cost is one Vertex AI Search call per contradiction, and that alone would
be a Backlog line. What makes it a checkpoint is where the answer lands:
`_citations_for`'s result goes onto the finding, so a bible contradiction
reaches the report carrying articles of territorial copyright law retrieved for
a query about narrative order. On screen that reads as a legal claim about a
continuity error. CP-026's own criterion already states the rule in the
neighbouring case — a bible contradiction "has no rights holder to resolve" —
and it has no legal question either. Ruling it now is also the cheap moment:
CP-029 wires the real adapter, after which every demo run pays for it.

SDD §4.1 step 5's closing sentence names one lookup as skipped and now names
both, so the specification stops describing a call the code does not make. One
sentence, carried as a criterion on the checkpoint that changes the behaviour,
on D17's and D19's precedent.

**D33. The unasserted `AnalysisReport.script` metadata is pinned where the
mutant lives; the gap it exposed in CP-029 gets its own criterion.** CP-026's
reviewer measured it: `version=99` leaves all 311 tests green, and no criterion
of CP-026 names `version`, `gcs_uri` or `jurisdiction_code`. Two different
properties hide behind one finding. The report carrying what `execute` was
given is CP-026's module (`analyze_script.py:142-149`), so it is one assertion
in CP-039, whose diff already opens that test file. The response carrying it to
the SPA is CP-029, and that checkpoint has no criterion naming the analyze
response body at all — SDD §4.1 step 8 makes it the payload "the SPA needs no
second call to render", so pinning its shape was missing rather than deferred.
Both are one line. Neither is a second attempt on a passed checkpoint.

**D34. `research.py`'s transport message gets the assertion `webhook.py`'s
already has. CP-042.** CP-035's reviewer proved the asymmetry by mutation:
replacing `research.py:104`'s `{error}` interpolation with `"boom"` leaves the
suite at 311 passed, while the same mutation on `webhook.py:39` fails
`test_connect_error_raises_notification_failed_with_a_connection_message`. The
research-side test asserts only what the message is *not*. This is §5's rule
exactly — production code with no test that fails without it — and it is the
same class CP-035's own review blocked on, one adapter over. One assertion, no
`src/` edit; `str(parallel.APITimeoutError)` is `"Request timed out."`, which
the reviewer observed while mutating.

**D35. The `walk_packages` docstring says what CP-038 measured. CP-042.**
`test_error_boundaries.py:65-69` claims `walk_packages` "swallows a package's
`ImportError` and silently drops it from the walk". CP-038's implementer and
reviewer both measured that it does not: the `ModuleInfo` is yielded before any
import, only packages are imported, so a broken leaf module always reaches
`_adapter_modules`'s own unguarded import, and what `onerror=None` suppresses
is recursion into a broken package's children. The test is correct and the
property it pins is real; only the explanation is wrong, and it is wrong about
the exact subtlety two turns were spent establishing. Left standing, it is the
document a later reader would use to reopen D29's premise — which is the same
failure D29 itself named, one layer over: a record that reports the opposite of
what it proves.

*One checkpoint for D34 and D35, not two.* Both are test-only, both are
dependency-free, and each is a few lines. Two turns for that is the cost D17
declined to pay for two lines of prose. The seam if a reviewer disagrees is the
file boundary.

**D36. The MVP ships with a mocked wiring mode, selected by `CLEARCUT_MODE`.
CP-043, plus four criteria on CP-030 and two on CP-031.** A user decision of
2026-08-31, relayed through the conductor: *"podes parar en mvp, mockear hasta
que conecte los servicios."* It is ranked the way D14's overturn was ranked — a
product decision the leader sequences, never one a leader triages away.

What it changes is one branch in `composition.py`. `CLEARCUT_MODE=mock` wires
in-memory implementations of the eight ports, seeded with the planted script of
SDD §8(d), and reads none of the twelve environment variables. `CLEARCUT_MODE=live`
is exactly what CP-030 already specifies, and it is what an absent variable
means. Both modes ship. Connecting a real service afterwards is an environment
change, not a code change, which is the property the decision was asking for.

*Why the default is `live`, and why an unknown value is fatal.* A deployment
that quietly serves a planted Ferrari because nobody set a variable is worse
than one that refuses to start naming the credential it wants. So mock is
opt-in, `CLEARCUT_MODE=demo` fails at startup naming both accepted values
rather than falling back to either, and mock mode says so in one startup
warning. A mocked service must be identifiable from its own logs.

*Why the in-memory implementations live under `src/`.* `composition.py` cannot
import from `tests/` — §2 rule 4 aside, `tests/` is not shipped, so a Cloud Run
image built from `src/` would import a module that is not there. `tests/unit/fakes.py`
therefore cannot be the answer, and the honest reading is that these are not
test doubles at all: the demo is their production use. They are
`src/clearcut/adapters/demo/`, they are CP-043's deliverable, and they get
their own tests like any other adapter.

*Why this is not the §4 violation it resembles.* §4 bans an interface with a
single implementation and an abstraction with a single caller. This is neither:
eight ports that already exist for real I/O boundaries gain a second
implementation, and the second one is what the 2026-09-07 demo actually runs
on. The failure §4 is pointing at here is drift — two implementations of one
contract diverging — so CP-043 binds each class to its port with D3's annotated
assignment, the mechanism that already catches arity, parameter types and
return types across the five live adapters. The package is seed data plus eight
thin classes. The moment one of them grows a rule its live counterpart does not
have, it has stopped being a mock and started being a second system.

*What mock mode must skip.* Everything that needs a service to exist: no
ClickHouse client is constructed, `ensure_schema` is never called, no
credential is read, no socket is opened. Asserted by clearing the environment
down to `CLEARCUT_MODE=mock` and nothing else.

*What mock mode must not skip: observability.* The demo's last thirty seconds
are a Grafana trace of the run, and the run is mocked, so spans living only
inside the live adapters would leave that beat with nothing to show. CP-031
gains it explicitly: the five stage spans and the four metrics appear in both
modes, with each demo adapter opening the same-named span as the live adapter
it stands in for. Five one-line duplications, and no wrapper layer — a
span-decorating class per port would be eight new types serving one purpose,
which is the abstraction §4 bans by name.

*The one panel that stays empty, and why that is correct.* `clearcut_gemini_tokens_total`
is derived from a model's usage metadata. In mock mode no model ran, so the
counter records nothing and the `extract` span carries no token attributes.
Seeding plausible token counts would put a fabricated number on a dashboard
shown to judges, in a product whose whole argument is that an unsourced
plausible answer is worse than none. Stage latency, findings-by-severity and
tracker-by-state all measure our own code and our own data, so all three stay
real in mock mode. Token spend is the panel that comes back the day a real
Gemini key lands.

*One checkpoint plus amendments, not two checkpoints.* The seed data and the
eight classes are one deliverable, one test file, and no dependency on anything
in flight — CP-043, dispatchable now. The mode branch is an `if` and two wiring
functions inside a file CP-030 is already writing; the graph was shaped once
before (CP-041's Notes) precisely to avoid reopening `composition.py` for one
constructor argument, and reopening it for one branch would repeat that mistake
on purpose. If CP-030 reaches 3/3, the split axis is live wiring in one
checkpoint and the mock branch in another.

### Settled 2026-08-31, the first terminal verdict of the project (D37)

**D37. CP-028 is SUPERSEDED downward. The specification moves to what the ports
support; the ports do not move to the specification. CP-044 re-lands
`EvaluateDelta` with the amended criterion, CP-045 corrects the ADR and SDD
§4.3, and persisting asset identity goes to the Backlog with a dated reason.**

CP-028's reviewer returned the first `BLOCKED` in this project and returned it
correctly: twelve of thirteen behavioural criteria survive mutation, the gates
are green at 386, and the one that fails is unreachable from inside the block's
`Files`. Criterion 5 requires a re-extracted finding to keep its `finding_id`
and its tracker state by matching `(category, normalized raw_text)` "even when
the asset moved to a different scene". No store holds that pair between runs.
`TrackerItem` (`domain/tracker.py`) carries neither field, `TrackerStore`
exposes no findings read, and the Backlog has recorded the root cause since
2026-08-30: no findings table in `infrastructure.md` §6 and no port for one.
The code joins on scene-number overlap instead, which is the only join the
ports can serve.

The counterexample is measured, not argued. v1 scene 2 carries a Quilmes
billboard as `EVT-002` at CLEARED. v2 edits the brand out of scene 2 and adds
scene 9 carrying it. The run returns `EVT-003` BLOCKED on scene 9 and leaves
`EVT-002` CLEARED with `needs_review` set on scene 2. One asset, two rows, and
the clearance does not follow it.

**Ruling: amend the criterion, not the schema.** Four grounds, weighed against
2026-09-07.

- **The demo does not exercise the case.** SDD §7 phase 5's exit condition is
  "uploading v2 with **one edited scene** re-analyzes exactly that scene and
  preserves CLEARED items". An edited scene keeps its number and its heading,
  so it joins as CHANGED and scene-overlap matching pairs it. The beat lands
  under the join as built. This is the same first ground D19 ruled on, and it
  is still the true one.
- **The other road reopens two `DONE` archives seven days out.** Persisting
  asset identity is a field on `TrackerItem` (CP-025, CP-036), two ClickHouse
  columns with a migration on an adapter CP-023 already shipped, a widened
  `latest_for_project` read, and then a re-do of `EvaluateDelta`'s matching on
  top. Four implementer turns and four reviewer turns minimum, on the critical
  path that CP-041, CP-030 and CP-031 all queue behind. An unpersisted field
  reads back empty, so there is no half of this worth landing.
- **§4 forbids building it now.** "Build exactly what the current checkpoint's
  acceptance criteria require" — and the criteria are the leader's to set. A
  stored asset identity exists to serve a case no demo beat runs and no other
  checkpoint reads.
- **The behaviour that ships is defensible on its own.** A moved asset is not
  dropped and not silently re-cleared. It mints a new item at BLOCKED, and the
  item it left behind stays open and flagged for re-review. A producer sees
  both rows. What it costs is a second clearance a human performs, which is
  work, not a wrong answer.

**The honesty conditions, which are the price of ruling this way.** A downgrade
that hides itself is worse than the gap it hides, and this project's own
argument (D31) is that an assurance without evidence behind it is the one
failure it cannot afford.

1. ADR 0007's Consequences section says plainly that a moved asset arrives as a
   new item at BLOCKED and gets cleared again. The paragraph landed in the
   blocked diff claims the opposite, verbatim from D19, and the ADR is
   `Accepted`. CP-045 replaces it with the text below.
2. SDD §4.3's carry-forward bullet stops describing an asset-identity match.
   Same checkpoint, same reason: the specification currently describes code
   nobody can write against these ports.
3. D19 gains a dated correction, recorded above rather than here so the next
   reader finds it where the false premise is. Its "permissions are not lost on
   renumbering" holds for scenes that keep their number, and that is the demo
   beat.
4. The stale item stops being a bare flag. CP-044 gives it a note naming the
   scene it was cleared against, so a producer reading a flagged CLEARED row
   learns why it is flagged. Today it carries `needs_review` and an empty
   `note`, which is non-silent but not diagnosable.

**Why two checkpoints and not one, against D17's and D19's own precedent.**
That precedent — one paragraph does not earn an implementer turn plus a
reviewer turn, so carry it as a criterion on the checkpoint whose behaviour it
describes — is what produced BLOCKING 2. The ADR paragraph rode into CP-028 as
criterion 11 among twelve behavioural ones, its box was ticked, and a false
claim reached an `Accepted` ADR. Prose that describes a behaviour needs a
reviewer who is reading the prose against the code and nothing else. CP-045 is
that turn. It is off the critical path, so the precedent's cost argument does
not apply here.

**Verbatim replacement for ADR 0007's Consequences section.** No em dash and no
literal `--`: the reviewer measured that `sdd.md`, `proposal.md` and all ten
ADRs contain zero em dashes, and that the blocked diff's ` -- ` substitution
made ADR 0007 the only planning document using it. The house form is neither,
so this text needs no dash.

> ## Consequences
>
> Scenes hash on content rather than position: `content_hash` covers the
> normalized text and nothing else, so a renumbered but unchanged scene
> produces the same hash.
>
> The join key is a separate question, and SDD Section 2 answers it
> differently: scenes join across versions on `number` plus `heading`.
> Renumbering a scene therefore does not merely move it, it changes its
> identity. The old number leaves as REMOVED, the new one arrives as ADDED,
> and the two equal hashes are never compared. Inserting a scene re-analyzes
> every scene below it.
>
> That compute cost is accepted, and clearance pays a second one beside it.
> Carry-forward matches a re-extracted finding to an existing tracker item by
> scene overlap, because no store holds a finding's category and text between
> runs: `TrackerItem` carries neither, and Section 6 of `infrastructure.md`
> defines no findings table. An asset that stays in its scene keeps its
> `finding_id` and its tracker state across versions, which is the case
> Section 7 phase 5 of the SDD demonstrates. An asset that moves to a
> different scene does not. It arrives as a new item at BLOCKED and a human
> clears it a second time, while the item it left behind stays open, flagged
> for re-review, and carrying a note naming the scene it was cleared against.
> Nothing is dropped and nothing is kept without saying so, and the repeated
> clearance is real work.
>
> REMOVED scenes keep their open items, because a cut scene can return in v3.
>
> Joining on the hash first would recover some of the wasted compute, but only
> for scenes renumbered and left otherwise untouched, and it would need a rule
> for two scenes in one version that hash alike, since `content_hash` is not
> unique within a version. Carrying a clearance across a move needs a stored
> asset identity: a category and a normalized text on `TrackerItem`, the
> columns behind them, and a read that joins on the pair. Neither is
> specified, so neither is built. Both are recorded as known limitations.
>
> Edits below scene granularity also cost full price; a single changed line
> re-embeds and re-analyzes the whole scene.

**Verbatim replacement for SDD §4.3's fourth bullet**, the one beginning
"Carry-forward matches by asset identity":

> - Carry-forward matches by scene: a re-extracted finding on a CHANGED scene
>   takes over the `finding_id` and the tracker state of an existing item
>   whose `scene_numbers` overlap the changed set. Matching on the asset
>   itself would need a stored category and normalized text per finding, and
>   no table holds them (section 6 of `infrastructure.md` defines none), so an
>   asset that moves to a different scene arrives as a new item at BLOCKED
>   while its old item stays open, flagged for re-review with a note.
>   Findings and permissions on unchanged scenes carry forward as they are. A
>   CHANGED scene whose tracker item was CLEARED keeps its state but gets
>   `needs_review` set to true and a notification, matching ADR 0007: the
>   clearance is neither silently kept nor dropped. New assets, and assets the
>   pipeline can no longer tell apart from new ones, get new EVT ids and start
>   at BLOCKED.

**And SDD §4.3's second bullet, for the same reason one bullet up.** That
bullet's parenthetical promises the old LoreStore rows for a CHANGED scene are
deleted before re-embedding. They are not: the frozen `LoreStore` port has no
`delete`, the Backlog has carried it as a known limitation since 2026-08-30,
and CP-044 does not build it either. Correcting one false sentence in §4.3
while leaving its neighbour standing would make this ruling a preference rather
than a rule, so CP-045 takes both. Verbatim replacement:

> - ADDED and CHANGED scenes are re-extracted, re-enriched, and re-embedded.
>   The design calls for deleting a CHANGED scene's old LoreStore rows first.
>   That part is not built, because the `LoreStore` port has no `delete`
>   method, so a changed scene leaves a stale row that later retrieval can
>   return as history.

**Most of the blocked diff is reusable, and CP-044's implementer should reuse
it.** `src/clearcut/application/evaluate_delta.py` and
`tests/unit/application/test_evaluate_delta.py` are untracked in the working
tree right now, and `src/clearcut/domain/tracker.py` carries the `noted` method
the REMOVED path needs. Twelve criteria passed mutation under two independent
runs. Deleting that and starting again would spend the turn re-proving work a
reviewer has already measured. The changes CP-044 asks for are the amended
criterion 5, the note on the stale item, the blank-note guard on `noted`, and
the module docstring. The modified ADR in the working tree belongs to CP-045
and must not ride along in CP-044's commit.

**The three non-blocking findings from the same review.**

*(a) A delta run's `report.findings` omits UNCHANGED scenes' findings. To the
Backlog, folded into the findings-table entry that already exists.* The root
cause is the same missing store: an UNCHANGED scene is never re-extracted, by
design, and nothing persisted its findings from v1. There is no cheap fix. The
response cannot carry them without a findings table, and labelling the payload
as partial would add a key that D30 and CP-041's second criterion forbid,
because `web/src/api/client.ts` renders both paths from one shape. What holds
in the meantime: the `tracker_items` in that same response cover every item in
the project, changed or not, so the clearance record the producer acts on is
complete. The findings overlay is the incomplete surface, and on a v2 upload
"what changed" is what the reader asked for.

*(b) `TrackerItem.noted` accepts a blank note where `with_draft_email` rejects
one. Into CP-044 as a criterion.* CP-044 opens `domain/tracker.py` and
`test_tracker.py` anyway, it is one guard and one test, and CP-044's own stale
-item note gives `noted` a second caller. The sibling's reason applies
unchanged: a version bump that stores nothing looks exactly like a version bump
that stored a value.

*(c) `evaluate_delta.py` at 386 lines against §4's 300-line guide, and
`execute` at ~38 statements against 30. Declined, and it does not become a
checkpoint.* §4 calls both soft and invites the argument. The file is long
because the delta algorithm has five scene-state paths and each one is a named
helper doing one thing; splitting it would produce a second module with one
caller, which §4 bans by name in the sentence above the size guides. CP-044
adds a note and a guard, so the file grows rather than shrinks. Recorded so the
next reviewer does not re-raise it as new.

*Not ruled this turn.* CP-043's review left three non-blocking items of its own
(a copyright citation beside the trademark one, the bare `KeyError` in
`InMemoryRightsResearch`, and a Notes overreach about project scoping). They
belong to the next leader turn, and they are named here so they are not lost
between one.

### Settled 2026-08-31, the second terminal verdict (D38)

**D38. The two vendor clients that connect during construction stay eager. The
live wiring becomes injectable, not lazy. CP-030 is SUPERSEDED into CP-048 and
CP-049.**

*The obstacle, reproduced rather than taken on trust.* Both halves of the
implementer's diagnosis are exact, and both were re-verified this turn against
this repo's own `.venv`:

- `clickhouse_connect`: `HttpClient.__init__` calls
  `super().__init__(..., autoconnect=True)` with the value written as a literal,
  and `autoconnect` is not a parameter of `HttpClient.__init__` at all
  (`inspect.signature(...).parameters` — checked). The base `Client.__init__`
  does take `autoconnect: bool = True` and guards `_init_common_settings` behind
  it, so the capability exists in the library and the HTTP subclass closes the
  door on it. `create_client` has no `autoconnect` parameter either. There is no
  public way to build this client without a connect-and-fetch-settings round
  trip.
- `langchain_google_community`: `BigQueryVectorStore`'s
  `@model_validator(mode="after") def validate_vals` calls `bigquery.Client(...)`,
  `self.embedding.embed_query("test")`, `create_dataset` and `create_table`.
  A pydantic after-validator runs inside `__init__`, and there is no skip flag.

So criterion 6 as written — build the app with dummy values, assert zero network
calls — and criterion 1's eager live wiring genuinely cannot both hold. The
implementer was right to stop.

*What the diagnosis missed, and it decides the ruling.* The adapters are not the
problem. `ClickHouseTrackerStore.__init__(self, client: _ChClient)` and
`BigQueryLoreStore.__init__(self, vector_store: _VectorStore, embeddings:
_Embedder)` both take an already-built vendor object behind a narrow local
`Protocol` and perform no I/O whatsoever. CP-023 and CP-024 already solved this
exact problem by pushing vendor construction out of the adapter. The only code
that must call the vendor constructor is `composition.py`. The fix is therefore
to apply the move those two checkpoints already made, one level further out —
not to invent a new mechanism.

*Options (a) and (b) are declined: the lazy wrapper is the wrong shape, and it
is wrong twice.* First, it contradicts a criterion of the same checkpoint.
Criterion 4 requires a missing or bad credential to fail **at startup naming
that variable, not at the first request**, and says outright that "a demo that
500s on the first upload because a secret was never set is the failure this
criterion exists to prevent." A lazily-constructed client moves exactly that
failure to the first upload. Installing an abstraction that undoes a criterion
the same block carries is not an unblock. Second, §4: two proxy classes with one
caller each, wrapping a urllib3-backed client and a pydantic model, each needing
its own tests and its own mypy-strict conformance proof, is "an interface with a
single implementation" and "an abstraction for one caller" — banned until a
checkpoint proves the need, and nothing here proves it.

*Option (c) is taken, with the hole in it repaired.* As the implementer phrased
it, (c) narrows criterion 6 and stops. That would leave criteria 1, 3, 5 and 7
untestable for the live branch: if the live graph cannot be constructed offline,
then nothing can assert that it wired the eight adapters, that two calls produce
independent instances, or that each mode wired the classes it claims by type.
Narrowing one criterion would quietly gut four. So the ruling adds the seam the
adapters already use: **the live wiring accepts the two connecting vendor
clients as an argument with a real default.** Production calls the real
constructors and connects eagerly; a unit test passes fakes and asserts the
whole live graph by type with no network. Plain constructor injection, which §4
endorses by name, and no new class.

*Eager connect is correct here, not merely tolerated.* This service cannot do
its job without ClickHouse, and criterion 4 already chose fail-fast. A client
that connects in `__init__` delivers that policy rather than fighting it: on
Cloud Run at `min-instances 0` a bad credential fails the revision loudly
instead of producing a service that accepts an upload and 500s on it.

*What D36 contributes.* The demo runs in `CLEARCUT_MODE=mock`, where no live
adapter is constructed at all, so the zero-socket guarantee the demo actually
depends on is the mock criterion — and that one is strictly stronger than
criterion 6 ever was, because it drives a whole `POST /api/analyze` request
through the app rather than only its construction. Criterion 6's real remaining
job is unit-test hygiene (§5: unit tests do no network), and injection delivers
that in full.

*Why this is a supersede and not a return to `TODO`.* AGENT.md §6 states that
`BLOCKED` is terminal and "the `leader` never returns it to `TODO`", and §7's
table gives `BLOCKED` exactly one outgoing edge: `SUPERSEDED`, one generation,
`Depth: 0` only. Those two rules are what remove the last unbounded back-edge
from the machine, and `./.claude/init.sh verify` proves it mechanically from
that table — an unblock that reset the status would make the proof false. So the
unblock has to be a split, and CP-030 is `Depth: 0`, which makes it eligible for
exactly one.

*The split axis is the one CP-030's own Notes recorded* — "live wiring in one
checkpoint and the mock branch in another" — written before anyone knew what
would block, and still right. CP-048 takes the app factory, the mode switch and
the mock branch: it needs no credential, it is dispatchable immediately, and it
delivers the entire demo path on its own. CP-049 takes the live wiring and this
ruling's seam. Both are `Depth: 1`, so if either blocks again the loop stops for
a human rather than splitting a second time.

*One consequence worth stating plainly.* Between CP-048 and CP-049, a
deployment that omits `CLEARCUT_MODE` gets a loud startup failure saying the
live wiring is incomplete. That is deliberate and it is the safe direction:
CP-030's criterion 7 chose "absent means live" precisely so a forgotten variable
never serves planted data, and an incomplete live branch that refuses to start
honours that better than one that silently falls back to mock.

### Settled 2026-08-31, one deferred finding from CP-048's PASS (D39)

**D39. The layer gate is narrowed to same-package siblings, as a checkpoint
rather than a Backlog line. CP-050.**

*The finding, reproduced.* `tests/unit/test_layer_boundaries.py:157` skips every
file whose parents include the adapters directory, so
`test_composition_is_the_only_module_importing_adapters` never examines an
adapter importing another adapter's package. CP-048's reviewer proved it by
planting `from clearcut.adapters.demo.in_memory import InMemoryTrackerStore` at
the top of `adapters/http/routes.py` and watching the suite stay green.

*Why a checkpoint and not the Backlog, seven days out.* CP-048's criterion 8
says the extension "turns §2 rule 4 from a convention into a gate", and CP-048
passed partly on that claim. Across packages the gate is nominal, so the
criterion currently promises more than it delivers — that is a contract
violation, not polish, which is the test my own filing rule applies. This
project has already ruled this exact class once: D29 filed CP-038 to make two
error-boundary guards fail on what they were written to catch, and the Active
note that carried it said a gate that cannot fail is the one kind of test worth
fixing before the deadline rather than after it. Nothing about that reasoning
has weakened.

*What it protects, concretely.* A live route holding a demo store is D36's exact
failure — the mocked service mistaken for a live one — and after CP-048 the demo
adapters are real, importable modules in the same tree as the live ones. This
gate is the only structural check standing between that import and a green
suite.

*The shape, and the trap in it.* Allow same-package, reject cross-package.
Exactly one legitimate adapter-to-adapter import exists today —
`adapters/demo/in_memory.py:26`, `from clearcut.adapters.demo import scenario` —
and it is written in **absolute** form, not relative. So the allowance has to
compare package identity, computed from the importing file, against the imported
dotted name. A narrowing that whitelists relative-import syntax instead would
fail on the tree the moment it lands, and one that bans all adapter imports
would fail on the same line.

*One thing folded in, and it is coupling rather than creep.* The Backlog's
`_package_for` pin moves into this block. The narrowed comparison is computed
*through* `_package_for`, so that function being correct stops being a coverage
nicety and becomes a prerequisite: under mutant C (`".".join(parts)`), which
survived all seven tests during CP-001's review, the new comparison
misclassifies packages silently and the gate goes quietly wrong in the direction
of permissive. Same file, same turn, one assertion.

*Ordering.* CP-050 is dependency-free and test-only, so it dispatches beside
CP-046 today. It goes **before CP-031**, because both edit
`tests/unit/test_layer_boundaries.py` and CP-031 adds `opentelemetry` to the
forbidden application prefixes in that same module. That is a file collision,
not a dependency.

### Settled 2026-09-01, the ten-item deferred queue and the empty board (D40–D49)

CP-049 landed on its third attempt (HEAD `8034344`) and emptied `## Active` of
checkpoints for the first time since CP-001. Every SDD phase-4 and phase-5
checkpoint is `DONE`. What is left is the subject of this turn: ten non-blocking
findings recorded across the last two days of reviews, sitting in archived Notes,
that no leader turn ever ruled on. A finding parked in a `DONE` block is the one
thing this loop's own rule forbids — a non-blocking finding becomes a checkpoint
or a dated declination, never a silence — so all ten are ruled below. One becomes
a checkpoint, six become dated Backlog entries, one is declined outright, and two
are editorial corrections to this file made in this turn.

The tiebreak is the one this file has used since 2026-08-30: does it protect the
2026-09-07 demo? Six days out, with the demo running mocked (D36), a live-path
polish item faces a **higher** bar than it did a week ago, not a lower one. An
empty board is not spare capacity looking for work. Every item promoted now costs
an implementer turn and a reviewer turn that the submission itself may need, and
the reviewer turn is the scarcer of the two — CP-049 spent three of them on one
checkpoint.

**D40. The env-var reconciliation is the only one of the ten that becomes a
checkpoint. CP-051.**

*The finding, reproduced.* `composition.py:196-205` reads exactly ten variables
through `_required_env`. `.env.example` holds twelve names and
`VERTEX_SEARCH_DATA_STORE_ID` is not among them; `docs/plan/infrastructure.md`
section 8's table holds the same twelve and is also missing it. So a deployer who
sets every documented variable gets the loud startup failure CP-049's criterion 5
built on purpose, naming a variable no document mentions. CP-049's implementer
disclosed this in the same turn that created the name, and both of its reviews
carried it forward untouched.

*And the same gap runs the other way.* `AGENT_BUILDER_AGENT_ID` is in
`.env.example:11`, in the section 8 table, and printed as a `.env` line by
`infra/provision_retrieval_plane.sh:218` — and nothing under `src/` reads it.
CP-022 built `VertexSearchGrounding` around a data store id, not an agent id. A
deployer is being told to obtain a value that changes nothing.

*A third surface, found while ruling this and folded in.* Section 9's deploy
command carries `GOOGLE_CLOUD_PROJECT`, `GEMINI_MODEL` and `GEMINI_MODEL_LITE` in
`--set-env-vars`, and `PARALLEL_API_KEY` and `CLICKHOUSE_PASSWORD` in
`--set-secrets`. That is five of the ten required. Fixing the table and leaving
that command as it stands would move the deployer's failure from the first
variable to the sixth, which is not fixing it. It is in scope because the
checkpoint's whole claim is that following the documents works.

*Why a checkpoint, six days out, when nothing else on this queue was promoted.*
This is the only item of the ten that breaks a person rather than a test.
Everything else is a coverage gap, a duplicated helper, or a warning — real, but
its victim is a future maintainer, and it fails in a direction someone will
notice. This one fails silently until the moment a deployment is attempted, which
on this calendar is the worst possible moment to discover it. The cost is also
small and mostly already paid: the provisioning script already computes the value
it fails to print (`DATA_STORE_ID="clearcut-legal-corpus"`, line 31) and already
prints one `.env` line at 218. It prints the wrong variable, not a missing one.

*Why the guard is bidirectional, and it is not scope creep.* A one-way test
(every required name is documented) fixes today's failure and leaves the door
open on the side `AGENT_BUILDER_AGENT_ID` came through. Both halves are the same
rule stated once — the documented set and the required set are the same set —
which is one behaviour, not two. The reverse half has exactly one honest
exception: `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS` are
read by the OTLP exporters themselves rather than by our code, deliberately, per
CP-031's criterion 1 and CP-049's attempt-1 ruling. The test names them in an
exception set with a comment each, rather than pretending they are unread.

*What this turn deliberately does not decide.* Whether `AGENT_BUILDER_AGENT_ID`
should be struck from the documented set or kept with a sentence explaining it.
Deleting the variable is not the same as deleting the provisioning step that
creates the Agent Builder app, and whether Vertex AI Search needs that engine for
the data store `VertexSearchGrounding` queries is a question for whoever holds
the console, not for a planning turn that cannot run the API. CP-051's criterion
therefore requires a decision and its one sentence, and puts the provisioning
call itself explicitly out of scope. A leader guessing here would be inventing
infrastructure facts to close a bookkeeping gap.

*Prose is in scope and blocking.* `docs/plan/infrastructure.md` is a document, so
`.claude/WRITING.md` governs the lines this checkpoint changes and its findings
block CP-051 rather than deferring, in the same way they blocked CP-045.

**D41. Three live env values no test can prove reach their adapter: Backlog, not
a checkpoint.**

*The finding.* CP-049's attempt-2 review found three hardcoding mutants that
survive the full suite: `PARALLEL_API_KEY` (`research.py:95-100` builds a
`Parallel` client and keeps only the client, never the key), and
`GOOGLE_CLOUD_PROJECT` in either `genai.Client` (`composition.py:231`) or
`VertexAIEmbeddings` (`composition.py:221`), both vendor objects. Closing them
needs a vendor-internal attribute read or a small adapter change.

*Why it waits, and the discriminator is what the mutant models.* Every mutant
CP-049 did close modelled **silence**: a demo store wired into a live use case
serves planted data and looks perfectly healthy, which is D36's entire argument.
These three model something else. A hardcoded `PARALLEL_API_KEY` fails
authentication on the first research call. A hardcoded project id either fails on
the first Vertex call or — in the realistic form, where a developer hardcodes
`clearcut-hack`, the one project this system has — behaves correctly by accident.
A surviving mutant whose most likely instance is indistinguishable from correct
behaviour is a weak reason to read vendor privates or to store a credential on an
attribute purely so a test can compare it.

*Recorded with the entry so a later turn does not re-derive it:* the two shapes
available are a vendor-internal read (`client.api_key`, `VertexAIEmbeddings`'s
pydantic `project` field — version-coupled, though the pins are exact `==`) or an
adapter change storing the value. The three `CLICKHOUSE_*` values are not in this
class and need nothing: they are consumed by the seamed client the test fakes,
and CP-049's criterion 6 kills a hardcoded substitution for them.

**D42. `answer_project_question`'s tracker asserted by type rather than identity:
Backlog, not a checkpoint.**

*The finding.* Wiring that use case to a second `ClickHouseTrackerStore(ch_client)`
instead of the shared instance leaves the suite green;
`test_build_live_use_cases_shares_the_seamed_clients_across_use_cases` covers
three use cases and not the fifth.

*Why it waits.* `ClickHouseTrackerStore` holds the client and no other state, so
two stores over one seamed client behave identically at runtime. The surviving
mutant is a no-op, not a latent defect the test failed to catch. The mutant that
*would* matter — a store over a second, real client — opens a socket and dies on
`_forbid_sockets` today. So the gap is one line of test strength against a
behaviour that cannot currently go wrong, which does not justify an implementer
turn and a reviewer turn on this calendar.

*Recorded because it protects CP-049's record:* attempt 1's required change said
"matching what the mock test does", and the mock sibling asserts by type too. The
implementer built exactly what was asked. Nothing was under-delivered.

**D43. The `VertexAIEmbeddings` deprecation warning: Backlog, not a checkpoint.**

`langchain-google-vertexai` is pinned `==3.2.4`, in a file whose convention is
exact pins, so the removal in 4.0.0 cannot reach this repo until a human edits
that line. Nothing before 2026-09-07 edits it. What the warning costs today is
one line on every live `create_app()`, on a path the demo does not run (D36). The
Backlog entry exists so that whoever performs the bump reads the reason first
rather than meeting it as an `ImportError`.

**D44. The six `_record_stage` duplicates, and `test_observability.py`'s copies
of the `conftest.py` helpers: Backlog, not a checkpoint.**

*The finding.* CP-031's reviews found `_record_stage` near-identically in five
modules plus a sixth variant `_record_stage_latency` in the extractor,
`_refresh_tracker_items_gauge` in two, and then — after the fix round —
`test_observability.py:61` and `:251` as byte-for-byte duplicates of the
`conftest.py` helpers that same attempt extracted.

*Why it waits, and the rule is being read correctly rather than conveniently.*
This is under-abstraction. Section 4 bans the opposite, and the reviewer said so
when filing it. "Duplicate twice, extract on the third" is a guide for code being
written; it is not a warrant to rewrite six modules that are finished. The
consolidation would touch five live adapters and the demo module, every one
`DONE` and mutation-verified, for zero observable behaviour change — the upside
is a shorter tree, the downside is reopening the instrumentation that took CP-031
two rounds and roughly sixty mutants to prove. That trade is wrong six days out
and it is wrong in a way that only shows up if it goes badly. The trigger that
makes it worth doing is a seventh span site.

**D45. A stage that raises records no latency: DECLINED, and the semantic is now
deliberate rather than accidental.**

CP-031's reviewer noted that every `_record_stage` call sits after its `with`
block, so `clearcut_stage_latency_ms` measures successful stage duration only,
and asked for a deliberate decision rather than a change. Here it is: **the
current behaviour is correct and stays.** Three reasons, in the order they carry
weight.

1. *The failure is not invisible.* The span is still opened and still recorded,
   and the exception marks it, so a failing stage appears in the trace view — which
   is the surface SDD section 8(d) actually puts in front of a judge.
2. *Recording failure durations into the same histogram would be worse than
   omitting them.* Without a `status` label a thirty-second timeout lands in the
   same distribution as a working stage and corrupts its percentiles. A metric that
   silently mixes two populations is a worse instrument than one with a stated
   scope.
3. *Adding that label is a spec change, not a fix.* CP-031's sixth criterion pins
   the four metrics to "those exact names and label sets", and SDD section 6 names
   them. Widening one is a decision about the specification, and no evidence on
   this queue argues for it.

Recorded here so the next reviewer who notices the asymmetry finds a decision
instead of an oversight. It is not filed to the Backlog: there is no work behind
it.

**D46. CP-046's criterion-4 import-time property, still unpinned: Backlog, not a
checkpoint.**

*The finding.* Hoisting `_default_build_dir()`'s body to a module-level constant
leaves the suite green, because the test that pins the parameter passes both
directories explicitly and cannot see the difference.

*Why it waits, and the comparison that decides it.* What the surviving mutant
costs is bounded and nearly nothing: the default build directory would be
computed once per process instead of once per call, and the repository root does
not move during a process. The criterion's stated purpose — a test can point the
build anywhere — is met and mutation-proven; only the "computed at import time"
half is unpinned. The instructive comparison is the `_package_for` pin, which was
also an import-time coverage gap and *was* promoted, by D39. It was promoted
because CP-050 made it load-bearing: the narrowed gate computes its allowance
through that function, so a wrong `_package_for` silently makes the gate
permissive. Nothing makes this one load-bearing for anything. The test shape is
recorded with the entry (importing `clearcut.composition` touches no filesystem)
so a later turn inherits it.

**D47. Widening the same-package adapter allowance to sibling modules: Backlog,
not a checkpoint — and it carries CP-050's other two notes.**

*The finding.* CP-050's gate compares the importing file's package against the
imported dotted name by exact equality, which is what its criterion 3 asked for.
The consequence is that a same-package sibling written any other way —
`from .scenario import DEMO`, `from clearcut.adapters.demo.scenario import DEMO` —
is reported as a violation it did not earn.

*Why it waits.* The gate errs strict, and strict is the right side to be wrong on
here. The failure mode of the current shape is a red gate on a legitimate import,
which stops a person for a minute and tells them exactly what it thinks is wrong.
The failure mode of widening it carelessly is a permitted cross-package import,
which is the silent failure D36's whole argument is built against and CP-050 was
filed to end. And the trigger cannot fire before the deadline: with `## Active`
holding one documentation checkpoint, nothing between now and 2026-09-07 writes
an adapter at all.

*Two things folded into the same entry, because one turn in that file should
settle all three.* CP-050's note 2: a parent-package import is rejected from
inside a module's own subpackage as well, where the criteria are silent — same
strict direction, worth one sentence wherever note 1 is settled. And
`tests/unit/test_layer_boundaries.py:6-9`'s module docstring still attaches the
carve-out to the `adapters/` package, which is the shape of the wholesale skip
CP-050 removed. It reads correctly if "its own siblings" is taken per module, so
it was recorded rather than raised — but it is stale prose describing a gate that
no longer works that way, and it should be corrected in the same turn.

**D48. The `## Active` preamble is rewritten, and the text it replaces is not
preserved.**

That preamble accreted across eight leader turns. It described nineteen
checkpoints, then fifteen, a parallel dispatch plan, a cut list ordered by what
the demo could survive losing, and two supersedes. Every checkpoint it names is
now `DONE` or `SUPERSEDED`, and the cut list has nothing left to cut — so as of
CP-049's archival it described a board that does not exist, which for a file
whose entire job is to be the loop's state is the worst kind of stale.

It is replaced rather than kept as history. Keeping it would make this file a
second account of a history the Archive already holds, and the Archive is the
account with the review evidence attached; two records of the same events is how
they drift apart, which is the reason this file forbids duplicating checkpoint
state into memory. The dispatch reasoning worth keeping was never really here
anyway — why CP-031 could not be re-cut is D14's amendment, why CP-049 became
cuttable and CP-048 did not is D38 — and those are decisions, in the section for
decisions, where they were argued.

**D49. `Attempts` counts rejections, not rounds. The archive is not renumbered.**

*The discrepancy, measured rather than asserted.* CP-031's second-round reviewer
flagged that the archive holds both conventions and asked the leader to settle
it. Counted across all fifty archived blocks: twenty-three record `0/3` and were
never sent back; twenty-two record `1/3` after exactly one `CHANGES_REQUESTED`;
CP-014 records `2/3` after two. That is forty-six. The other four use the ordinal
reading — CP-045 and CP-050 record `1/3` having never been rejected at all,
CP-046 records `2/3` after one rejection, CP-049 records `3/3` after two.
Forty-six to four.

*One block settles it on its own.* CP-028 was `BLOCKED` by its reviewer rather
than sent back, and that reviewer wrote the counter's meaning out in the verdict
line: "BLOCKED, routed to the leader. **Not an attempt.**" The block sits at
`0/3` after a full review round. A field that a completed review can leave at
zero is counting rejections, not rounds.

*The dominant convention is also the only permitted one, so there is no conflict
to escalate.* AGENT.md section 6 step 4 increments `Attempts` on
`CHANGES_REQUESTED` and on nothing else, and section 7's table writes the edge as
`IN_REVIEW → TODO (+1 attempt)`. A leader rules inside that contract, never
against it. Both grounds point the same way.

*The rule, now stated in this file's Editing rules where an implementer will
actually meet it:* `Attempts: n/3` is the number of `CHANGES_REQUESTED` verdicts
the checkpoint has received. A checkpoint that passes its first review stays at
`0/3`. The third rejection sends it to `BLOCKED`.

*Archived counters are left exactly as written.* Renumbering them would mean
editing terminal blocks a reviewer signed, to correct a bookkeeping field whose
value changed no outcome in any of the four cases. One consequence is worth
recording so a retrospective does not misread it: CP-049's reviewer wrote that it
"lands on its last permitted turn" at `3/3`, and under the settled convention it
had taken two rejections and landed with one turn still in hand. It passed either
way. The margin was one turn wider than the block says.

### Settled 2026-09-01, the three findings CP-051's PASS deferred (D50–D52)

CP-051 passed on its first attempt with zero blocking findings, and its reviewer
recorded three non-blocking ones. AGENT.md section 6 is explicit that a leader
adds checkpoints only for a new human goal or a `BLOCKED` checkpoint, **never in
response to a `PASS`** — so however good these are, none of them can reopen the
board this turn. That rule is not a formality. It is one of the two edges whose
absence would let the loop run forever, and a leader who routes around it because
a finding looks worthwhile has removed a termination guarantee to save a
document.

So all three are ruled here, and none is declined. Each changes what a maintainer
or a deployer actually meets, which is the test this file has applied since D40;
none is taste. Each carries the trigger that would justify promoting it, so
whoever picks one up is deciding on the trigger rather than on the fact that it
is still sitting here.

**D50. `infra/README.md:40` tells a deployer to copy a variable that no longer
exists: Backlog, bound to the D17 entry already open on that file.**

*The finding.* Step 7 still says to copy `AGENT_BUILDER_AGENT_ID` from the
script's output into `.env`. CP-051 struck that variable from `.env.example`,
from the section 8 table, and from the script's `.env` line, so the instruction
now names a value the output no longer prints and nothing reads. The implementer
disclosed it and correctly left it alone — criterion 4 named three surfaces and
that file was in neither them nor `Files`.

*Why it is not the same class as the gap CP-051 just closed, which is the whole
question.* CP-051's gap was a deployer setting every documented variable and
still getting a startup failure: a hard stop, discovered at the worst possible
moment. This one fails safe. A deployer follows step 7, looks for a variable that
is not in the output, and is confused — but the service starts, because nothing
requires that variable, which is precisely why it was struck. Wasted minutes, not
a broken deployment. That difference is the reason this is a Backlog line and
CP-051 was a checkpoint, and it is worth stating rather than leaning on the
section 6 prohibition alone: the rule decides the routing this turn, but the
severity decides whether a human should care.

*Bound rather than free-floating.* The Backlog already holds a fix for this exact
file and this exact numbered list — D17, attached to the Cloud Run deploy entry:
the run order jumps to `gcloud storage ls "gs://clearcut-legal-corpus/**"`
without ever telling a human to upload the legal PDFs into that bucket first.
Two stale steps in one procedure, so one turn in that file should fix both. Same
reasoning as D47, which folded three notes into one entry for one turn in
`test_layer_boundaries.py`.

**D51. The environment guard's AST filter skips five call shapes in silence:
Backlog, with the fix shape recorded.**

*The finding.* `tests/unit/test_environment_contract.py:44-53` matches only a
string-literal first argument to a bare `_required_env` name. The reviewer
measured five shapes that are each skipped without a word: a variable argument,
an f-string, `name=` passed as a keyword, a loop over a tuple of names, and a
module-qualified call. The docstring says "literal name", which is true, and does
not say what happens to everything else.

*Why this is the sharpest of the three, and still not a checkpoint.* The failure
direction is the bad one. A guard that silently stops covering a call site goes
quietly permissive, and what it stops covering is the exact drift CP-051 was
filed to end — a required variable outrunning its documentation. This is the same
shape as D39's mutant C, where `_package_for` returning the wrong package made
the layer gate silently permissive; that one was promoted, but only because
CP-050 made it load-bearing for a gate's correctness in the same turn. Nothing
makes this one load-bearing today, for a reason I verified rather than assumed:
all ten `_required_env` call sites in `composition.py` are bare calls passing a
string literal (`composition.py:196-205`), so the filter's coverage is complete
as the tree stands. The hole is entirely in the future.

*The fix shape, recorded so it is not re-derived, and it is the reviewer's rather
than mine.* Do not widen the parser to understand five more shapes. Assert that
every `_required_env` call site passes a string literal, and let the unhandled
shapes announce themselves. That keeps the parser simple and converts silence
into a loud failure, which is the property that was missing — a gate that cannot
cover something should say so rather than skip it.

**D52. Section 9's deploy command is guarded by nothing, and the reverse
direction keys on the wrong thing: Backlog, one entry, both halves.**

*Half one.* The new guard covers `.env.example` and the section 8 table. Section
9's deploy command is a third surface, it is correct today, and nothing holds it
there. That matters more than a third surface usually would, because section 9 is
the surface D40 found last and found **by inspection** — it drifted once already,
unnoticed, while the other two were being reconciled. What limits the risk is
that section 9 lives in the same document as the table the guard does cover, so a
maintainer adding a variable gets a loud failure that drags them into the right
file, three sections from the command. That is a weaker guarantee than a test and
a stronger one than nothing.

*Half two, and it is a trap with a misleading message.* The reverse direction
keys on `_required_env` rather than on "read anywhere under `src/`". So a
maintainer who documents `CLEARCUT_MODE` — which `composition.py:78` genuinely
reads — gets a failure saying nothing requires it. Loud rather than silent, which
is the right direction, but the message asserts the opposite of the truth, and a
loud failure that misdescribes its own cause costs more than a quiet one that
does not fire. `OPTIONAL_ENV_VARS` is the one-line fix the reviewer names.

*One entry, because one turn in that file should settle both.* They are the same
test module and the same question — what the guard's authority actually covers —
and splitting them would guarantee the second is rediscovered while the first is
being fixed.

### Settled 2026-09-01, the board reopens on a new human goal (D53)

**D53. The Browser MVP is a new goal, not a Backlog promotion the loop took on
its own. CP-052, CP-053, CP-054.**

*What changed.* The user approved a plan to make ClearCut runnable and demo-able
on localhost and chose the Browser MVP scope. That is the one thing the terminal
preamble named as able to reopen this board: a human starting a new goal. The
loop did not restart itself, no `PASS` produced these checkpoints, and no
`BLOCKED` block was reopened — which matters, because those are the two edges
section 6 forbids and the reason the board could be trusted to stay closed.

*The trigger that fired.* The Backlog's SPA-surfaces entry has carried its own
promotion note since 2026-08-31: "a mocked MVP the user can only see through
`curl` is not the MVP the decision asked for", unblocked since CP-048 landed and
named the first promotion candidate for the next leader turn. D36 changed what it
waited on, and nothing has waited on anything since. This is that promotion,
authorized where it has to be — by the human, not by a leader deciding the
Backlog looked ready.

*The approved plan is the contract.* It lives at
`~/.claude/plans/analyze-the-code-and-starry-bentley.md`, grounded in verified
exploration with file:line evidence behind each claim. Where a criterion below
and that plan disagree, the plan wins and the criterion is the defect. What
follows adds test names, signatures and failure paths to it; it does not
renegotiate its scope.

*Why three checkpoints and not one.* The work splits on two clean seams that are
also review seams. CP-052 is Python, packaging and prose, and it is verified by
running the thing from a fresh clone. CP-053 is a type contract with no rendering
in it, verified by `tsc` and vitest. CP-054 is the rendering, verified in a
browser. One checkpoint spanning all three would be reviewable only by a human
doing all three jobs at once, which is how a review turns into a rubber stamp six
days out. Three is also the number the plan prescribes.

*Why not five.* The obvious further split — one checkpoint per surface — was
considered and declined. The three surfaces share `App.tsx`'s state, one
stylesheet, and one `init.sh` edit, so splitting them creates three checkpoints
that collide on the same three files and cannot be dispatched in parallel
anyway. All cost, no benefit.

*The dependency ruling, which is the one place I depart from the brief's
framing.* The brief offered CP-053 a dependency on CP-052 "for ordering
cleanliness" and left the call to me. **CP-053 depends on nothing.** The two open
disjoint file sets — CP-052 touches `main.py`, `pyproject.toml`, `.claude/init.sh`,
`README.md`, `.env.example`, `docs/plan/infrastructure.md` and two Python test
files; CP-053 touches `web/` only — and CP-053's gates are `npm run typecheck`
and `vitest`, neither of which needs an entrypoint, a `.env`, or a running
server. A reviewer who wants to check the repaired types against a live response
can use the command that already works today
(`env CLEARCUT_MODE=mock PYTHONPATH=src ./.venv/bin/flask --app clearcut.composition run`),
which is exactly the command CP-052 exists to replace and which works regardless.
Declaring a dependency that does not exist would serialize two checkpoints that
can run side by side and spend a turn of the six days remaining on tidiness. So
**CP-052 and CP-053 dispatch in parallel, today.**

*CP-054's dependencies are real, and one of the two is a file collision rather
than a dependency — stated separately, following D39's precedent.* It depends on
**CP-053** genuinely: its components import `postAnalyze`, `patchTrackerState`,
`postTrackerAction` and `postQuestion`, and none of them exists until CP-053
lands. It depends on **CP-052** only because both edit `.claude/init.sh`'s
`check()` — CP-052 adds `main.py` to the mypy invocation, CP-054 adds the two npm
gates. Same function, same file. Not a real dependency, and recorded as a
collision so a later turn can reorder them freely if the collision is resolved
another way.

*Three declinations carried from the plan, recorded so they are not
re-litigated.* **Lazy vendor imports / an optional-dependency split for a slim
mock install** — it rewrites `composition.py`, a `DONE` module that CP-049 spent
three attempts and two full mutation batteries proving, for zero demo value; the
mock demo already runs with the full install. **gunicorn** — `main:app` at module
level is what a WSGI server needs and it is already there, so adding the server
now is building for a deploy no checkpoint has yet been written for. **Tailwind**
— its Backlog trigger has not fired; CP-054 hand-rolls roughly a hundred lines of
CSS instead, which is the smaller thing that the surfaces actually require. Each
is a live application of section 4's YAGNI rule rather than a judgement about
whether the thing is good.

*What this does not change.* The Backlog's other entries keep their triggers and
none of them fires here. In particular D51 stays open — CP-052 adds `CLEARCUT_MODE`
to `OPTIONAL_ENV_VARS`, which is D52's one-line fix landing on its ruled trigger,
but it does not touch the AST filter's silent skips, which is a different entry
with a different trigger.

### Settled 2026-09-02, the localhost plan's deferral queue and the board closing a second time (D54–D62)

CP-052, CP-053 and CP-054 are all `DONE` and committed (`2172574`, `f3f025e`,
`1362bc1`; HEAD `a4ad34d`). The approved Browser MVP plan is delivered, and
`## Active` is empty again — by completion this time, the same as after CP-051,
not by anything being abandoned.

Their six reviews left ten non-blocking findings. Nine become dated Backlog
entries, grouped into eight because two of them must be fixed together; one is
declined outright. Five days remain to 2026-09-07, and the tiebreak is D40's:
**does it break a person or a test before then?** With the demo now running in a
browser rather than over `curl`, one clause of that test has changed and it is
worth stating — "a person" now includes a judge clicking something, not only a
deployer reading a document. Two of the ten were flagged on that basis and both
were checked by hand rather than ruled from the summary.

**D54. `load_dotenv()`'s no-override contract is unpinned: Backlog, and it
belongs at the top of that list.**

*The finding.* `main.py:14` — removing the import and the call outright leaves
the whole unit suite green, and `load_dotenv(override=True)` is equally
invisible while no `.env` exists.

*Why it is the most serious of the nine, and why it still waits.* The no-override
default is what makes the README's own `CLEARCUT_MODE=live ./.venv/bin/python
main.py` beat a copied `.env` carrying `CLEARCUT_MODE=mock`. Flip that default
and a live invocation silently serves planted demo data while the operator
believes they are looking at real services — which is D36's named failure, the
exact class this project has spent CP-049, CP-050 and a supersede closing. So the
property is load-bearing and proved by nothing.

It waits anyway, on the narrowest possible ground: the mutant requires someone to
edit that line, and nothing between now and the deadline opens `main.py`. That is
a statement about the calendar, not about the risk. Whoever touches that file
first should close this before doing anything else, which is why it is written
first in the Backlog block rather than in finding order.

**D55. `PORT` is undocumented, and the test that covers it depends on `.env`
being absent: Backlog as one entry, because fixing either alone makes things
worse.**

*The two findings.* `main.py:22` — `PORT` is a new environment variable no
document records, invisible to CP-051's guard because that guard parses
`_required_env` calls in `composition.py` only, so this is a documentation gap
rather than a guard failure. And `tests/unit/test_entrypoint.py:93` —
`test_port_defaults_to_8080` depends on the absence of an untracked file:
planting a root `.env` containing `PORT=7777` reddens it against an unmodified
`main.py`, because `load_dotenv()` injects `PORT` into the cleared environment
before `_port()` reads it.

*Why they are one entry, and this is the ruling that matters here.* They look
independent and they are not. Documenting `PORT` in `.env.example` is an
instruction to put `PORT` in a real `.env` — which is precisely the condition
that reddens the test. **Doing the documentation half alone would take a latent
environment dependence and start actively triggering it**, turning a green suite
red for a developer who did exactly what the documentation told them to. So the
entry carries both halves and says plainly that the test's env-independence
lands first, or with it, never after.

**D56. The environment trio is atomic in one direction only: Backlog.**

*The finding.* Removing `CLEARCUT_MODE` from `OPTIONAL_ENV_VARS` while both
documents keep it reddens three tests, but removing it from `.env.example` while
`OPTIONAL_ENV_VARS` keeps it stays green. CP-052's criterion said "any
intermediate commit is a red tree", and that holds for one ordering rather than
both.

*Why it waits.* A criterion that over-claims is the shape D39 once promoted, so
the comparison is worth making rather than dodging. D39's gate was protecting a
silent failure — a cross-package adapter import serving demo data on a live
route. This one protects a variable that is *optional* by construction: lose
`CLEARCUT_MODE` from `.env.example` and a deployer gets live mode by default,
which fails loudly on `GOOGLE_CLOUD_PROJECT` rather than quietly on anything.
Loud, bounded, and behind a trigger nothing fires in five days.

**D57. `README.md:47` still names a bare `python` in the live-mode command:
Backlog, and it is the cheapest thing on this list.**

*The finding.* CP-052's attempt 2 fixed line 18 to `./.venv/bin/python` for mock
mode and left line 47 — the live-mode paragraph — with a bare `python`, which
resolves to nothing in a shell where the virtualenv was never activated. Its
reviewer ruled it out of that checkpoint's criteria scope rather than as
acceptable, which is a different thing and is why it is here.

*Why it waits, despite breaking a person.* It does break a reader, and that
normally wins. What holds it back is *which* reader: the live-mode paragraph is
addressed to someone with twelve credentials configured, and the demo runs
mocked. Nobody walks that path before 2026-09-07. The remedy is one path prefix,
and attempt 1's own sentence is the wording to reuse when it is opened: do not
leave a boot command that only works in an already-activated shell.

**D58. The `as` cast cannot see a missing or renamed fixture field, and
`fixtures.test.ts` now contradicts itself: Backlog.**

*The finding.* Deleting `project_id` from `tracker.json[0]`, or renaming it to
`projectId`, leaves typecheck and the suite green — the cast catches a *wrong
type*, never a missing or renamed key. The analyze fixture has an
`Object.keys` assertion; tracker items have no counterpart. That is the residual
hole in the very masking CP-053 was filed to close. Alongside it, the comment at
`fixtures.test.ts:19` still claims the cast catches "a renamed or missing field
at any depth", and now sits fifteen lines above a newer comment correctly saying
the cast performs no excess-property check. Both sentences are true about
different things and the file reads as contradicting itself.

*Why it waits.* The fixtures do match the wire on keys and types today, so the
hole is guarding against a future edit rather than covering a present defect, and
nothing before the deadline edits them. The stale comment is the part that costs
a reader something now — but it costs a reader of a test file, and the correction
belongs in the same turn as the assertion it describes.

**D59. The three `/api/` spellings in `client.test.ts` `it()` titles: DECLINED.**

*The finding.* `client.test.ts:68,89,151` spell out `/api/analyze`,
`/api/tracker/:itemId` and `/api/question` in their test titles, a second
spelling of a path that could drift silently from `client.ts`.

*Why this one is dropped rather than deferred.* `architecture.test.ts` permits it
deliberately — the gate requires a quote character immediately before the
segment, so prose mentions are outside its scope by design, and the pre-existing
atoms mention `src/api/` the same way. The titles are accurate today. And the
worst case if one drifts is a misleading label on a test whose actual behaviour
is pinned through `client.ts`'s functions, not through its own name; no
assertion weakens, no gate goes quiet, nothing a user or deployer meets changes.
That is taste, and a Backlog that collects taste stops meaning anything. Recorded
as declined with its reasoning, which is the same treatment D45 got — a finding
ruled on its merits rather than filed because filing is easier than deciding.

**D60. The web fixtures have drifted from the wire scenario: Backlog, and it
cannot reach the demo.**

*The finding, confirmed wider than first reported.* Committed `tracker.json`
carries `item_001`/`fnd_001`-style ids where the live scenario serves
`EVT-001`..`EVT-003`; documents "Product placement release", "Synchronization
license" and "Location permit" where the wire serves "Trademark Clearance Form",
"Synchronization License" and "Continuity Revision"; and notes on items 2 and 3
("Awaiting quote from publisher.", "Permit approved through end of shoot week.")
where the live continuity item carries `""`.

*Why it waits, and this is the load-bearing fact I verified rather than
assumed.* **The fixtures are imported by five `.test.tsx` files and by no
production module** — checked directly this turn. Nothing a judge sees comes from
them; the browser talks to the real server, which serves `scenario.py`. So the
drift cannot reach the demo, and the one genuinely dangerous case it might have
masked is independently covered: CP-054 pins the empty-value row through a
hand-built `TrackerItem` literal in `TrackerRow.test.tsx:16-30`, which mutation
testing confirmed catches a raw `undefined`.

*What is honestly wrong with it, stated rather than smoothed over.* CP-053's
criterion flipped these fixtures to "server truth" specifically so the
conformance test would stop masking drift, and five days later they are not
server truth. That is a criterion that decayed rather than a nicety that was
never met, and the next person to write a web component against these fixtures
would be writing against fiction. That is exactly the trigger.

**D61. `index.css` styles the two badges through their `data-testid` hooks:
Backlog.**

*The finding.* `index.css:129-130` selects `[data-testid="risk-badge"]` and
`[data-testid="state-badge"]`, because the atoms expose no class name and that
was the only handle available without editing files outside CP-054's list.

*Why it waits, and why it is a real smell rather than a style preference.* It
couples presentation to a testing hook, so a future test-only refactor — renaming
or removing a `data-testid`, which anyone would consider a safe change — silently
breaks the demo's appearance. That cross-coupling is worth removing. It waits
because removing it means editing `StateBadge` and `RiskBadge`, two `DONE`
atoms with their own tests, and nothing in five days touches either the atoms or
the stylesheet. The fix is to give the atoms a class name, and it belongs to
whoever owns them.

**D62. `TrackerDashboard`'s `handleNotify` is unpinned: Backlog, and the residual
risk is smaller than the measurement suggests.**

*The finding.* Gutting `handleNotify` alone leaves all 50 tests green, so those
four lines are the one segment of that container still unpinned.

*Why this was checked by hand rather than ruled from the report.* It was flagged
as demo-adjacent, and the notify button is on screen — a judge can click it even
though it is not in the scripted beat. "Low probability" is not evidence, so I
read the code. `handleNotify` (`TrackerDashboard.tsx:75-79`) is a
literal-for-literal twin of `handleDraftEmail` above it: same
`postTrackerAction` call, same
`.then((updated) => setItems((current) => (current === null ? current :
replaceItem(current, updated))))`, same `.catch(handleMutationError)`, differing
only in the action string. Both of its ends are independently pinned —
`client.test.ts:130-133` pins `postTrackerAction(id, "notify")` sending
`{action: "notify"}`, and `TrackerRow.test.tsx:108-111` pins the button reaching
`onNotify` with the item id — and `handleDraftEmail`, the identical join, is
pinned end to end.

*The ruling.* Verified correct by reading, unpinned by testing. Those are
different claims and both are true: the demo will not break, and a future edit to
those four lines would not be caught. One container test mirroring the
draft-email one closes it. Recorded also because the reviewer's restraint was
right: attempt 1 wrote one bounded finding and closed it, the named remedy was
delivered, and expanding the finding set afterwards is the goalpost move section
6 depends on reviewers not making.

### Settled 2026-09-02, a user-ordered design pass that did not go through the loop (D63–D65)

**D63. The SPA was redesigned on a user order, as delegated-direct work rather
than as a checkpoint. Committed `349da37`.**

*What happened.* The user rejected the shipped UI in plain terms — no Don Norman
principles, no Vercel style, almost no CSS — and ordered a design pass. It was
executed as delegated-direct work with a full adversarial review and committed as
`349da37`: 13 files under `web/`, 705 insertions against 164 deletions. Geist and
Geist Mono typography, a token-based design system in `web/src/index.css`,
`TrackerRow` restructured into a labeled `dl` grid, pending states on every
mutation with three new load-bearing tests, and semantic badge classes replacing
the `[data-testid]` selectors.

*Recorded here because it is outside the loop, and that has to be visible.*
Fifty-four checkpoints sit in the Archive, each with a block and a review behind
it, and until now `git log` and that Archive told the same story. `349da37` is
the first commit in this repository that changes application code with no
checkpoint behind it. A reader reconciling the two would otherwise find a
substantial `web/` commit with no block, which is the same class of confusion
CP-050's reviewer flagged when HEAD asserted a checkpoint state with no code
behind it — the mirror image of it. So it is written down rather than left to be
discovered.

*Why it was legitimate, stated precisely, because the distinction matters.*
AGENT.md section 6 binds **agents**: a leader may not open checkpoints in
response to a `PASS`, and `BLOCKED` never returns to `TODO`. Those rules exist to
stop the loop restarting itself. They do not bind the human. A user who looks at
the delivered UI and says it is not good enough is not an agent routing around a
termination guarantee; they are the person the whole loop reports to. The board
was terminal, the work was ordered directly, and it took the route the user's own
routing rules select for two-or-more non-trivial files: one delegated writer, one
adversarial review, one commit. Recording it as a decision keeps the ledger
honest without pretending it was a checkpoint it never was.

*The review verdict, and the one deviation that was argued rather than waved
through.* The review found a single blocking finding — a dead class combined with
an ID-specificity problem — and it was remedied exactly as prescribed and
verified before the commit landed: 53 of 53 tests, 6 of 6 gates. The deviation
worth recording is `index.css` at **490 lines**, well past section 4's soft file
guide of 300. The reviewer accepted it explicitly and on a stated reason rather
than by omission: it is a flat token-then-component stylesheet whose cascade a
split would actively harm, because the token block has to precede every component
that reads it and splitting introduces an import-order dependency that nothing
would check. Section 4's size guides are labelled soft and say to argue if wrong.
This is what arguing looks like, and the argument is accepted here too.

*One detail worth keeping, because it is evidence the ledger is being read.* The
stylesheet's own header comment records the rule it follows and cites D61 by
number. A ruling written in this file on 2026-09-02 reached the implementer of a
change made the same day, and came back cited in the artifact. That is the
Decisions section doing the job it was built for.

**D64. The label colons `TrackerRow` lost in the `dl` restructure: Backlog,
optional, and ranked low on purpose.**

The restructure into a labeled `dl` grid dropped the colons that previously
followed each label. The reviewer raised it as optional. It stays optional here: a
`dl` grid already separates term from description visually and structurally, so
the colon is redundant punctuation in the new layout rather than a lost cue. What
would change that is evidence, not taste — if the flat labels read ambiguously to
anyone looking at the screen, `dt::after { content: ":" }` restores them in one
declaration without touching the markup. Filed so the option is on record with
its remedy; not filed as a defect, because nothing yet says it is one.

**D65. A 490-line hand-maintained stylesheet is checked by nothing: Backlog, and
this is the one of the two that has teeth.**

*The gap, verified this turn rather than inferred.* `.claude/init.sh` names no CSS
gate and `web/package.json` declares no CSS tooling — neither stylelint nor
prettier over `*.css`. `check()` runs ruff, ruff format, mypy, pytest, `npm run
typecheck` and `npm test`, and not one of them reads a stylesheet. The file that
grew from roughly 138 lines to 490 in a single commit is the only substantial
artifact in this repository that no gate inspects.

*Why it matters more than a lint preference, which is the whole argument for
filing it.* The review's one blocking finding was a **dead class**. That is
precisely the defect class a CSS gate catches mechanically and that human review
catches only by luck and diligence — this time diligence won, and the finding was
caught and fixed before the commit. The gap is not hypothetical and its
consequence is already on the record: an unchecked stylesheet is exactly what let
that class through to review in the first place. The same reasoning ran in D44
about `init.sh check` running zero frontend gates, which is how CP-053's contract
drift survived every earlier review; adding those gates is what surfaced it.

*Why it still waits.* It is tooling, five days from the deadline, on a file that
is correct today and that nothing is scheduled to touch. *Trigger:* the next
`index.css` edit — whoever opens that file next should add the gate before
changing a rule, not after.

---

### Settled 2026-09-03, the loop could not tell a service from a fake (D66)

**D66. A `live` test tier, a gate that runs it, and the contract clauses that
make it binding. Delegated-direct work on a user-approved plan, not a
checkpoint.** The board was terminal at fifty-four checkpoints, and the user
asked why a finished product could not reach a single service. The audit that
followed is the reason this entry exists.

*What the audit found.* The `clearcut-hack` project does not exist — `gcloud
alpha bq datasets list --project=clearcut-hack` returns "not found or deleted".
`tests/integration/` held one test whose body is `assert True`. All fourteen
adapter test files use hand-written fakes, so no adapter had ever contacted the
service it wraps. And two identifier bugs guaranteed to fail on the first real
call were sitting in `main`, invisible to all 477 passing tests: the Document AI
processor id, which `document_ai.py:149` needs as a full resource path while
`infra/provision_data_plane.sh:136-140` strips it to a bare id; and the Vertex
AI Search data store id, which exists in three mutually incompatible forms
across the test, the provisioning script and the adapter.

*Why this is not a failure of any agent.* Every checkpoint's acceptance criteria
were satisfiable with a hand-written fake, and §6 step 5 ends the loop on an
empty board. Nothing ever asked whether the product worked, so nothing answered.
D41 named the failure mode exactly — *"a demo store wired into a live use case
serves planted data and looks perfectly healthy"* — and filed it as Backlog. It
was right, and filing it was not enough.

*What changed.* `pyproject.toml` declares a `live` marker and defaults to
`-m "not live"`, so the fast loop stays offline while the tier stays
collectable. `tests/live/` holds one module per Phase 1 adapter, each asserting
on a value a fake provably cannot produce — the Gemini token count the fake
leaves as `None`, a `groundingChunks` citation URI, the `content_hash` BigQuery
stored and returned. `./.claude/init.sh live` is the gate. AGENT.md §5 makes a
live test mandatory for any adapter checkpoint *in its acceptance criteria*,
because §4 binds an implementer to those and to nothing else; §9 adds the box;
reviewer.md gains item 10 and the `EVIDENCE:` line gains a `live` slot.

*A second instance of the same defect, fixed in passing.* `check()` reported a
missing tool through `note`, which increments neither counter. A machine with no
ruff, no mypy, no pytest and no `web/node_modules` printed `0 passed, 0 failed`
and exited success. Absence read as success there too. Those four branches now
call `no`; verified on a bare directory, which reports `0 passed, 4 failed` and
exits 1.

*What was deliberately not done.* No new `Status` value. `.claude/lib/termination.py`
re-proves the §7 table on every `verify`, and a marker plus a gate leaves that
proof untouched — `init.sh verify` still returns 87 passed, 0 failed.

---

### Settled 2026-09-03, the board reopens to make the submission true (D67)

**D67. The submission runs live on the analyze path. ADR 0011, and CP-055
through CP-060.** A user goal, following the SDD rewrite that made the state
legible. The board reopens for the second time in its history, on the same
mechanism D53 used: a human approving a plan.

*What forced it.* `docs/plan/sdd.md` now grades itself against the user's bar,
and the grade is one section `DONE`, every port `WIP`, three endpoints and all
four verification checks `MISSING`, and no phase meeting the exit criterion it
wrote for itself. `infrastructure.md` section 11 requires "runtime proof that
calls are real and not mocked" in the submission, and mock mode cannot supply
that however honestly it is labelled.

*Why §7 is the reframing and not a new standard.* All five phase exit criteria
already demanded a real service, in the words their authors chose. Nothing was
under-specified. The phases were reported complete against a gate that could
not evaluate their own exit conditions, which is D66's defect seen from the
other end.

*What was ruled out, and why that is written down.* ADR 0011 cuts
`POST /api/projects` and `GET /api/scripts/{script_id}`: project ids are strings
the analyze request already carries, and the analyze response already carries
the ScriptView payload, which is why the SPA renders without either. Bible
ingestion becomes an infra script (CP-057) rather than
`POST /api/projects/{id}/bible`, so the endpoint stays `MISSING` and the SDD
keeps saying so. A producer cannot upload a bible in the demo. That is a real
product gap and the right trade at four days.

*Why only one of the four known defects is in scope.* CP-056 fixes the three
unguarded SDK calls because live traffic is what turns them into a 500 reading
"internal error" while a judge watches. `ContinuityCheck`'s missing
instrumentation, `EvaluateDelta`'s untested failure paths, and `Notifier`'s
missing live test are all real, all recorded in SDD sections 3 and 6, and all
deferred. Widening CP-056 to cover them is the failure mode this decision
exists to prevent.

*Dispatch order is not dependency order.* CP-056 goes first because it is the
only one of the six needing no cloud account, so it proceeds while provisioning
happens.

---

### Settled 2026-09-03, what the first live runs taught (D68-D72)

**D68. Gemini 3 answers only on the `global` endpoint. `composition.py` keeps
two locations.** Probed against the real API: `gemini-3.7-flash`,
`gemini-3.1-flash-lite` and `gemini-3-flash-preview` all return `404 NOT_FOUND`
at `us-central1` with "your project does not have access to it", and all answer
at `global`; the 2.5 family answers at both. ADR 0002 noted this for
`gemini-3.1-pro-preview` alone, so its note was narrower than the fact and is
now amended. `_GENAI_LOCATION` is separate from `_GCP_LOCATION` because the
BigQuery dataset and the embeddings do not exist at global, and a test asserts
the two differ. The models were right; the region was wrong.

*How it presented.* The first live call this project ever made failed, and
CP-056's translation turned a bare 404 into `ExtractionUnavailable` naming the
cause instead of the 500 it would have been the day before. The defensive work
paid for itself on its first real exercise.

**D69. `CLICKHOUSE_HOST` is normalised in code, not documented in a footnote.**
The Cloud console's Connect panel shows a full URL and
`clickhouse_connect.get_client(host=...)` prepends the scheme itself, so
pasting what the console gives produces `https://https://host:8443` and fails
DNS on the literal string "https". `composition._clickhouse_host` accepts bare
host, either scheme, a port, a trailing slash or whitespace. Fixed here rather
than in the runbook because the console is where every operator copies from and
a footnote does not survive a copy-paste.

**D70. `infrastructure.md` §9's IAM list was less than half of what a deploy
needs.** It names four runtime roles and no build roles at all. The first
`gcloud run deploy` failed `PERMISSION_DENIED` because the default compute
service account could not read its own source upload. Nine roles were required:
`cloudbuild.builds.builder`, `storage.objectViewer`, `logging.logWriter`,
`artifactregistry.writer`, `documentai.apiUser`, `aiplatform.user`,
`bigquery.dataEditor`, `storage.objectAdmin`, `discoveryengine.viewer`. Also
`cloudbuild.googleapis.com` is not among the seven APIs
`provision_data_plane.sh` enables.

**D71. Cloud Run's default request timeout is shorter than the pipeline.** A
real analyze against the deployed service returned HTTP 504 at exactly 300
seconds. Enrichment is a sequential loop and Parallel's `core` processor takes
77 to 169 seconds per rights lookup. Raised to 3600s. The user ruled on
2026-09-03 that the demo pre-runs the analyze rather than the pipeline being
made faster: dropping to the `base` processor and enriching concurrently is the
better product and is a behaviour change to the partner-track call four days
from the deadline. Recorded rather than done.

**D72. Every API path is a resource. A user ruling on 2026-09-03.**
`POST /api/analyze` and `POST /api/question` were RPC verbs; the resource is a
script version and a question. `project_id` moved from the body and query
string into the path, which is the substantive half: it names the collection
being written to rather than a field of the thing written, and a blank project
is now a routing concern that never reaches a handler. Two tests that asserted
400 from body validation now assert 404 from routing, and both still prove that
no adapter is called. The user chose the full rename over two narrower options
after being shown it touched 37 files.

**D73. CP-058 stays BLOCKED for a human. Not superseded.** Depth 0,
Attempts 0/3. The implementer shipped the dashboard JSON, the `--dry-run`
provision script, unit tests that pin the four real metric names, and a live
receipt test that skips without `GRAFANA_URL` / `GRAFANA_TOKEN`. Criteria 2–4
are Grafana-side: one live analyze's five stage spans under one trace id, a
non-zero `clearcut_gemini_tokens_total`, and the four panels
`infrastructure.md` §10 names. A JSON file is not those panels.

The missing piece is not more code. `.env` and Secret Manager hold only the
OTLP pair (`OTEL_EXPORTER_OTLP_ENDPOINT` / `OTEL_EXPORTER_OTLP_HEADERS` →
`otlp-gateway-prod-sa-east-1.grafana.net`). That Basic user is a numeric
instance id and the token is `glc_`. It authenticates to
`https://grafana.com/api/instances` and lists zero stacks; hosted-metrics by
that instance id is 403. Grafana's dashboard and datasource-query APIs need
`https://<slug>.grafana.net` and a `glsa_` service account token. D6 already
said Grafana Cloud is a human signup; this is that signup's second half.

Superseding would split a credential wait into smaller credential waits, which
§6 B forbids. The human action: create a Grafana Cloud service account with
dashboards:write and datasource query, set `GRAFANA_URL` and `GRAFANA_TOKEN`,
run `infra/provision_grafana_dashboard.py` and
`pytest -m live tests/live/test_grafana_receipt_live.py`. Do not reuse the
OTLP pair as `GRAFANA_TOKEN`. Independent IN_REVIEW work (CP-055, CP-056,
CP-057, CP-060) continues. CP-059 stays TODO until CP-058 is DONE; it also
needs a human `NOTIFY_WEBHOOK_URL`.

**D74. The board reopens a third time, on 2026-09-04, and CP-061 through
CP-077 close none of CP-055 through CP-060.** The new goal is the approved plan
"ClearCut API by domain: RESTful partition and MVP coverage". The state the
leader found, by reading `git log` and the working tree rather than the board:

- Statuses as written, unchanged by this turn, because only the agent named in
  §7 may move one: CP-055 `IN_REVIEW`, CP-056 `IN_REVIEW`, CP-057 `IN_REVIEW`,
  CP-058 `BLOCKED`, CP-059 `TODO`, CP-060 `IN_REVIEW`. No reviewer has passed
  any of them. Nothing below fabricates a `DONE` for work a reviewer never saw.
- The service is deployed: revision `clearcut-00005-sqx`,
  `https://clearcut-813918777633.us-central1.run.app`. The live adapter tier
  was 10 passed, 0 skipped at `337bddd`.
- Four commits landed outside the loop, joining `349da37` (D63) in the set
  `git log` reports and the Archive does not: `fbc1d34` and `bee965b` on
  2026-09-03 (the OpenAPI document, Swagger UI, and the D72 resource rename),
  `79aacb1` and `29c1f9a` on 2026-09-04 (the stylelint gate, and an 8(d) live
  test tightened to assert what a real model produces). CP-060's block already
  records that the deployed revision carries the rename.
- The tree is dirty: this file, `docs/plan/infrastructure.md`, `infra/README.md`
  and five `web/` fixture and test files are modified, and CP-058's four
  Grafana artefacts are untracked. An implementer starting CP-061 inherits
  that, and none of it collides with the new file sets.

The relationship is stacking, not replacement. CP-055–CP-060 are the live-tier
and deploy goal (ADR 0011). CP-061–CP-077 are the API-shape goal on top of the
same service, and they will require a second deploy — that is CP-077, not a
re-run of CP-060. Reviewers of CP-055–CP-060 judge them against their own
criteria as written; the new work neither satisfies nor invalidates any of them.
CP-058 stays `BLOCKED` for the same human credential (D73) and CP-059 stays
`TODO` behind it, unaffected by everything below.

**D75. ADR 0011's cut of projects, script reads and bible writes is reversed,
deliberately, and the reversal gets its own ADR.** ADR 0011 cut
`POST /api/projects`, `POST /api/projects/{id}/bible` and
`GET /api/scripts/{script_id}` to reach a live analyze path by the deadline.
That path is live, and the three cut endpoints are exactly what the mockup's
Projects list, New Project wizard and finding detail need; `docs/plan/sdd.md` §4
has been reporting them MISSING throughout. The Active preamble's instruction
"do not add endpoints ADR 0011 cut" applied to that goal and is now superseded
for this one. `docs/plan/adr/product/0012-api-partitioned-by-domain.md` amends
0011 rather than editing it, because an ADR that quietly changes its own mind
stops being a record.

**D76. `POST /api/tracker-items/{id}/actions` is split into sub-resources, and
the two unimplemented actions get no route at all.** An `action` enum in a
request body is a verb endpoint carrying four behaviours through one path, and
two of the four (`generate_document`, `stakeholder_link`) return 500 by
decision — a documented server error for a feature that was never built. The
replacement is two resources: `POST .../email-drafts` (201, the drafted item)
and `POST .../notifications` (201 with `sent_at`, 400 on a blank `reason`, 502
when the notifier is down). The other two stay in Backlog with **no route**, so
an unimplemented feature answers 404 by absence rather than 500 by decision. A
500 tells a client the server is broken; 404 tells it the truth.

**D77. The tracker key defect: `ReplacingMergeTree ORDER BY item_id` silently
merges two projects' items into one.** `tracker_items` is keyed on `item_id`
alone (`adapters/clickhouse/tracker.py:76-77`) while item ids are `EVT-NNN`
sequential *per project* (`application/evaluate_delta.py:97-103`). Two projects
both produce `EVT-001`, and on the next background merge ClickHouse keeps one
row — the other project's clearance history is gone, with no error anywhere.
`TrackerStore.latest(item_id)` has no project filter, so the top-level
`PATCH /api/tracker-items/{item_id}` route cannot even ask the right question.
`script_versions ENGINE = ReplacingMergeTree(version) ORDER BY project_id` is
the same defect in a second table: every version but the last collapses, which
is why versions cannot be listed at all.

The fix is three parts and they must land together or the data stays wrong:
`ORDER BY (project_id, item_id)` for `tracker_items`; `ORDER BY (project_id,
script_id)` for `script_versions` with the `(version)` argument dropped so every
version survives and `latest` picks the maximum client-side; and
`latest(project_id, item_id)` on the port, so the query carries the filter the
key now expects. ClickHouse cannot alter `ORDER BY` in place, so this is a
DROP-and-CREATE migration (CP-067) executed against the deployed service only
after the human confirms it (CP-077). The proof is a live test, not a unit test:
two projects each holding `EVT-001` must both survive `OPTIMIZE TABLE
tracker_items FINAL`, which forces the merge that today's key loses rows to. No
fake can fail that assertion, which is the point of §5.

**D78. `AnalyzeScript` and `EvaluateDelta` go to eight and nine constructor
parameters, over §4's ≤ 4 guide, on purpose.** They are already at seven and
eight, and adding `scripts: ScriptStore` makes each one worse. The only way to
get under the guide is a facade port bundling the stores, which §4 forbids
outright ("a port only for a real I/O boundary", "no interface with a single
implementation"). Between a soft size guide and two hard rules, the guide loses,
and it loses visibly here rather than silently in a review. §4 calls the size
guides soft and says to argue if wrong; this is the argument.

**D79. `composition.py` passes 300 lines, and does not get split.** §2 rule 4 is
a hard rule: wiring happens in exactly one place, no DI container, no service
locator. Fourteen use cases wired for two modes cannot be both single-file and
under 300 lines. The soft guide yields to the hard rule. The one extraction
allowed is mechanical: `create_app` delegates blueprint registration to
`_register_api(app, graph, mode)` in the same file. Splitting the graph across
modules to satisfy a line count would reintroduce the many-places wiring §2.4
exists to prevent.

**D80. Four limits are deliberate, and each has its reason recorded so it is not
re-litigated as an oversight.** (1) Analysis stays synchronous — `POST
.../scripts` returns 201 after the pipeline runs; a 202 plus a job resource is a
second bounded context and is deferred. (2) The five existing use cases do not
gain a project-existence check this round: it would add a `ProjectStore`
dependency to each, and an unknown `project_id` currently analyzes rather than
404s. That is a real gap, and it is a follow-up checkpoint once the SPA creates
projects, not a widening of any checkpoint below. (3) `jurisdiction_code` stays
required in the scripts and questions request bodies; the SPA defaults it from
the project rather than the server inferring it. (4) A v2 script's `GET` returns
the delta's findings, matching what its own `POST` returned (D37 follow-up), not
a recomputed full set.

**D81. The four parallel domain units share three files, and the shared lines
are additive.** CP-071 through CP-074 have disjoint file sets except
`composition.py`, `tests/unit/test_composition.py`, and the `DOMAINS` tuple in
`adapters/http/openapi.py`, where each adds one graph field, one line per mode
branch, one blueprint argument, one tuple entry and one assertion. Placement
rule that keeps the rest disjoint: a serializer or schema with one consuming
domain lives in that domain's module; one used by two or more lives in
`serializers.py` / `schemas.py`. Merge the four serially. A conductor running
them in parallel resolves those three files by hand, in checkpoint order, and
runs the gates after each merge.

**D82. Seventeen checkpoints for the plan's seven units, and where each split
falls.** The plan's CP-A alone spans a domain module, four ports, three
adapters, the demo tier, the fakes, two constructors, composition and two infra
scripts — that is not one implementer turn, and a checkpoint too big to finish
is a checkpoint that burns three attempts and lands as `BLOCKED` at Depth 0 with
its split budget already spent. The mapping: CP-A → CP-061..CP-067, CP-B →
CP-068..CP-070, CP-3a → CP-071, CP-3b → CP-072, CP-3c → CP-073, CP-3d → CP-074,
CP-C → CP-075..CP-077. Every edge the plan states is preserved; the splits only
add edges inside a unit. Two seams carry the risk: CP-069 is a pure move whose
invariant is that the served `(path, method)` set does not change, and CP-070 is
where the behaviour changes, proved live. CP-072 is the heaviest single
checkpoint left (three use cases plus multipart upload); if it blocks, it is a
Depth 0 checkpoint and can still be split once.

**D83. The HTTP modules are adapters, and §5's live-test rule reaches them
through CP-077, not through a `tests/live/` file per module.** §5 says an
adapter checkpoint is not `DONE` without a `tests/live/` test that reaches the
real service. For `adapters/gcp/storage.py` that service is GCS and the rule
applies literally — every store and storage checkpoint below names its live test
and the server-assigned value it asserts. For `adapters/http/` there is no
external service: the blueprint *is* the service, and its real-service proof is
an HTTP request to the deployed revision. So the HTTP checkpoints are proved by
their Flask test-client suites, named individually, plus CP-077's checklist
against `https://clearcut-813918777633.us-central1.run.app`. The one exception
is CP-070, which changes a ClickHouse query as well as a route: it names a live
test, because the store half of it is exactly the kind of defect D77 describes
and a test client cannot see it.

---

## Active

**Six checkpoints. The board reopened on 2026-09-03, on a human goal, for the
second time in its history.**

The goal is ADR 0011: run the analyze path live for the 2026-09-07 submission.
`clearcut-hack` exists (number `813918777633`). The live adapter tier was 10/10
against real services at `337bddd`, and that evidence no longer holds at HEAD.
The 2026-09-05 re-run found the gate reporting green having contacted nothing.
With the gate corrected the tier is 9 passed, 5 skipped, 0 failed of 14 in 92
seconds; the Parallel long-poll failure seen earlier that day does not
reproduce. Every skip names a missing variable:
`CLEARCUT_LIVE_SCRIPT_GCS_URI` (2), `NOTIFY_WEBHOOK_URL` (1), `GRAFANA_URL`
and `GRAFANA_TOKEN` (3). CP-055 and CP-056 were returned CHANGES_REQUESTED that day and are back at
TODO, 1/3. CP-057 sits IN_REVIEW. CP-060 is DONE. CP-058 is BLOCKED waiting on a
human Grafana Cloud service account (`GRAFANA_URL`, `GRAFANA_TOKEN`); the OTLP
write pair cannot provision or query the dashboard (D73). Independent reviews
continue while that waits. CP-059 stays TODO until CP-058 is DONE; it also
needs `NOTIFY_WEBHOOK_URL` in `.env`.

Do not widen CP-056 to ContinuityCheck instrumentation, EvaluateDelta failure
paths, or a Notifier live test. Do not supersede CP-058: the obstacle is a
credential, not mixed scope. The web-product-ui plan does not touch this board.

**Seventeen checkpoints, from 2026-09-04. The board reopened a third time,
on a second human goal, while the first one is still IN_REVIEW.** CP-061
through CP-077 come from the approved plan "ClearCut API by domain: RESTful
partition and MVP coverage": the API, its OpenAPI document and
`src/clearcut/adapters/http/` are partitioned into six bounded contexts, every
path becomes a resource with correct status codes, the ClickHouse tracker key
defect is fixed, and the resources the docs and the MVP need are added.

The two goals stack rather than compete, and D74 records exactly how. Nothing
below moves a status on CP-055 through CP-060; those six are judged against
their own criteria by the reviewer who holds them. The line above forbidding
`POST /api/projects`, `POST /api/projects/{id}/bible` and
`GET /api/scripts/{script_id}` bound the ADR 0011 goal and is reversed for this
one by D75 — those three endpoints are now required work (CP-071, CP-074,
CP-072). The deployed revision `clearcut-00005-sqx` already serves the D72
rename and the Swagger UI; CP-077 deploys again on top of it, after a
destructive ClickHouse migration the human must confirm first (D77).

Dispatch order: CP-061 and CP-062 are independent and may run together. Then
CP-063 → CP-064 → CP-065 → CP-066 serially, with CP-067 free to run beside
CP-065 and CP-066 once CP-064 is `DONE`. CP-068 → CP-069 → CP-070 serially.
Then CP-071, CP-072, CP-073, CP-074 in parallel, merging their three shared
files serially in checkpoint order (D81). Then CP-075 and CP-076 in parallel,
and CP-077 last.

### CP-055 — Provision every Google Cloud resource the live graph reads
- Status: TODO
- Attempts: 1/3
- Depth: 0
- Layer: infra
- Depends on: -
- Acceptance:
  - [x] `clearcut-hack` exists with billing linked, and
        `gcloud alpha bq datasets list --project=clearcut-hack` returns
        `clearcut` instead of "not found or deleted".
  - [x] `infra/provision_data_plane.sh` and
        `infra/provision_retrieval_plane.sh` have both run for real. Both are
        idempotent, so a second run reports every resource as already present
        and creates nothing.
  - [x] `.venv/bin/python infra/provision_tracker_schema.py` has created
        `tracker_items` and `script_versions` in a real ClickHouse Cloud
        service.
  - [x] `.env` carries all ten required variables, and
        `DOCAI_PROCESSOR_ID` and `VERTEX_SEARCH_DATA_STORE_ID` are the full
        resource names `test_identifier_agreement.py` demands, taken from the
        scripts' own output rather than retyped.
  - [x] Failure path, and the only automated proof the console-only step was
        done: a query filtered to a jurisdiction with no corpus documents
        returns zero results. `tests/live/test_vertex_search_live.py:55` is
        that test. If `jurisdiction` was never marked Indexable it returns
        Argentine statutes instead and the test fails.
  - [x] Gate: `./.claude/init.sh live` runs 10 tests with credentials present.
        Every one that skips names the variable it still needs.
- Files: `.env` (untracked), `docs/plan/infrastructure.md` if a step proves
  wrong in practice
- Notes: The scripts exist and are unit-tested against `--dry-run`. This
  checkpoint is the first time any of them touches a real project, so the
  likeliest outcome is that a documented step is wrong. Amend
  `infrastructure.md` when that happens rather than working around it.

  Grafana Cloud and ClickHouse Cloud have no automation and are created by
  hand. That is stated in `infrastructure.md` sections 6 and 10 and is not a
  gap this checkpoint closes.

  **Partly done, 2026-09-03.** `clearcut-hack` exists (project number
  `813918777633`) with billing linked. Created and verified by querying each
  resource rather than by reading script output: both GCS buckets, the
  `clearcut` BigQuery dataset, the Document AI OCR processor, seven Secret
  Manager containers, the Vertex AI Search data store, and the
  `clearcut-project-qa` engine. Both documents imported into branch 0.

  **The Notes above predicted a documented step would prove wrong. Two did.**

  *`provision_retrieval_plane.sh` was a silent no-op.* Application Default
  Credentials carry no quota project, so Discovery Engine answered every call
  `403 PERMISSION_DENIED` with `reason: SERVICE_DISABLED` — naming the wrong
  cause, because the API was enabled and only the token was incomplete. The
  script discards response bodies through `curl_auth_post`, so it printed its
  success banner while creating nothing. Adding `x-goog-user-project` turned
  the 403 into a 404, which proved both halves at once: auth was the problem,
  and the resource genuinely did not exist. Fixed on all four curl helpers,
  committed `ca7648e`.

  *Enabling an API and calling it are minutes apart.* The data-plane script
  enabled Document AI and then failed to create the processor in the same pass,
  printing `<not-yet-created>` with no error. Both scripts are idempotent, so
  `infrastructure.md` and `infra/README.md` now say to run each one twice.

  **An unplanned content gap.** The corpus bucket was empty and
  `provision_retrieval_plane.sh` dies on an empty manifest, but nothing in the
  repo says where legal documents come from. Sourced two official Argentine
  laws through the Parallel MCP: Ley 11.723 (copyright, from `ign.gob.ar`) and
  Ley 22.362 (trademarks, from `portaltramites.inpi.gob.ar`), covering both the
  "Hotel California" sync-licence finding and the Ferrari trademark finding.
  `build_manifest.py` derived `jurisdiction: "argentina"` correctly from the
  prefix. **Only Argentina is populated**; the other nine jurisdictions have no
  documents, which is what makes CP-055's zero-result criterion testable.

  **What is left, and why none of it is agent work.** Four criteria stay `[~]`.
  Application Default Credentials do not exist on this machine, and
  `gcloud auth application-default login` is an interactive browser flow, so
  every Python SDK in the live path cannot authenticate. The console-only
  Indexable toggle has no API. ClickHouse Cloud, Grafana Cloud and a Parallel
  API key are external signups. The identifier fix from `3dca760` did validate
  against real API responses: `DOCAI_PROCESSOR_ID` and
  `VERTEX_SEARCH_DATA_STORE_ID` both resolved as full resource names.

  **Reconciled 2026-09-03 (leader).** The four `[~]` above were ticked in
  `f8c12d0` and the evidence still holds. ADC exists at
  `~/.config/gcloud/application_default_credentials.json`. ClickHouse tables
  exist (live tracker tests compiled at 21:04). The Indexable toggle is proven
  by `tests/live/test_vertex_search_live.py`. `./.claude/init.sh live` was 10
  passed, 0 skipped at `337bddd`. The paragraph above is the record of what
  blocked this morning, not of what blocks now. Status stays IN_REVIEW; a
  reviewer marks DONE. `.env` still has `NOTIFY_WEBHOOK_URL` empty — that is
  CP-059's skip, not this gate (the ten adapter tests do not build the
  notifier).

  **CHANGES_REQUESTED 2026-09-05 (reviewer).** The 337bddd evidence was real
  when recorded; it no longer holds at HEAD. Gates re-run: `init.sh check` 7
  passed / 0 failed (564 passed, 14 deselected). Live re-run twice, and the two
  runs disagree — which is the finding.

  1. *Criterion 6 fails as written.* `./.claude/init.sh live`, run verbatim,
     executed **zero** live tests: `14 skipped, 564 deselected`, every skip
     citing `GOOGLE_CLOUD_PROJECT` / `CLICKHOUSE_*` / `PARALLEL_API_KEY` as
     unset. The script still printed `Result: 1 passed, 0 failed`. Cause:
     `.claude/init.sh:281-291` activates `.venv` but never loads `.env`, and
     `tests/live/conftest.py:30` reads `os.environ` only. No file in the repo
     documents sourcing `.env` first. The gate this criterion names therefore
     reports green having contacted nothing — the §5 failure the live tier
     exists to close. Required change: make the credentials reach the gate the
     criterion names (load `.env` in `live()`, or document and criterion-name
     the exact sourcing command), so the gate cannot be green on zero contact.
  2. *The count is wrong even with credentials.* With `set -a; . ./.env`:
     **8 passed, 1 failed, 5 skipped** of 14 — not "10 tests". Verified
     passing against real services: both BigQuery, all three ClickHouse, the
     Gemini extractor, both Vertex Search. Failing:
     `test_parallel_research_live.py` — `ResearchUnavailable: Parallel Task API
     request failed: Connection error`, reproducibly at ~60s inside the
     `task_run.result` long-poll, while `task_run.create` succeeded. Auth and
     reachability are fine, so this reads as a 60s idle cut rather than a code
     defect — but it cannot be shown green here, and criterion 6 requires that
     it is. Required change: establish the live tier green under the credential
     set the criterion claims, or re-scope the criterion to the tests CP-055
     actually provisions and name the Parallel poll as a separate checkpoint.
  3. *Criterion 4 fails.* `.env` does not carry every variable the live tier
     needs: `CLEARCUT_LIVE_SCRIPT_GCS_URI` is unset, and it alone skips
     `test_document_ai_live.py`. The Document AI processor is a resource
     **this** checkpoint provisioned, and no live test has exercised it in this
     run. Required change: put `CLEARCUT_LIVE_SCRIPT_GCS_URI` in `.env` (and in
     `.env.example`, which omits it) pointing at the planted screenplay.
  4. *The `NOTIFY_WEBHOOK_URL` claim is half right.* It is true it does not
     affect the eight tests that ran. It is not the only thing skipping
     `test_end_to_end_live.py` — that skip cites `NOTIFY_WEBHOOK_URL,
     CLEARCUT_LIVE_SCRIPT_GCS_URI`, and the second one is CP-055's, not
     CP-059's. Required change: correct the note, or close finding 3 which
     removes it.

  Verified sound, needing no action: criterion 1 — `gcloud alpha bq datasets
  list --project=clearcut-hack` returns `clearcut-hack:clearcut` (and
  `clearcut_temp`). Criterion 3 — the three ClickHouse live tests passed, so
  `tracker_items` and `script_versions` exist. Criterion 5 — substance holds:
  `test_a_jurisdiction_with_no_documents_grounds_nothing` passed, the KR filter
  genuinely raised `EnrichmentMissing`, which is an assertion no fake satisfies.
  Non-blocking: that criterion cites `test_vertex_search_live.py:55`, but line
  55 is the citation test; the zero-result test is at line 71.

  Non-blocking, for the leader: `live()` in `.claude/init.sh` counts an
  all-skipped pytest run as `1 passed` in its Result line, contradicting its own
  comment at lines 276-280 that an all-skipped run is "reported as such rather
  than counted as proof". Separate checkpoint — it is init.sh's defect, wider
  than CP-055.

### CP-056 — Translate every SDK exception the three bare adapters can raise
- Status: TODO
- Attempts: 1/3
- Depth: 0
- Layer: adapters
- Depends on: -
- Acceptance:
  - [x] `VertexSearchGrounding._ground`, `GeminiSceneExtractor._extract_batch`
        and `GeminiContinuityCheck.check` each catch what their SDK raises and
        re-raise a domain error. No `google.genai` `APIError`, no
        `json.JSONDecodeError`, and no `KeyError` from model output crosses the
        port.
  - [x] One test per adapter proves an `APIError` becomes the adapter's
        existing `SourceUnavailable` subclass, so the route returns 502 rather
        than 500. Each test fails without the change.
  - [x] A model response that is not JSON raises the adapter's domain error,
        not `JSONDecodeError`. One test per adapter.
  - [x] A model response naming a `scene_number` outside the batch raises the
        adapter's domain error, not `KeyError`. This is the likeliest of the
        three in practice, because it needs only a hallucination rather than
        an outage.
  - [~] `ParallelRightsResearch` also catches `APIResponseValidationError`,
        which sits beside the two exceptions it already handles and currently
        escapes to a 500.
  - [x] `test_error_boundaries.py`'s contract walk still passes: every adapter
        exception subclasses exactly one domain error type.
  - [x] Gate: pytest, ruff, ruff format, `mypy src tests infra main.py`. No
        live test is required, because these paths are provable with the
        hand-written fakes already in each test file.
- Files: `src/clearcut/adapters/gcp/vertex_search.py`,
  `src/clearcut/adapters/gemini/extractor.py`,
  `src/clearcut/adapters/gemini/continuity.py`,
  `src/clearcut/adapters/parallel/research.py`, and their four test files
- Notes: Dispatch this first. It is the only checkpoint here that needs no
  cloud account, and it is the defect most likely to show on camera: live
  traffic is exactly what turns an unguarded call into a 500 reading "internal
  error" while a judge watches.

  ADR 0011 ranks the other three known defects below this one.
  `ContinuityCheck`'s missing span and metric, `EvaluateDelta`'s untested
  failure paths, and `Notifier`'s missing live test all wait until after the
  submission. Do not widen this checkpoint to cover them.

  **Implemented 2026-09-03.** Three new `SourceUnavailable` subclasses, one per
  adapter: `GroundingUnavailable`, `ExtractionUnavailable`,
  `ContinuityUnavailable`. Each is separate from the adapter's existing error,
  which names a recoverable defect in an otherwise valid response; these name
  the call not completing. `GroundingUnavailable` is deliberately not
  `NoGroundedSource`, because that one is `EnrichmentMissing` and would degrade
  a finding to "ungrounded" when the truth is that nobody asked. Ten new tests,
  508 passing, all six gates green.

  **One criterion is marked `[~]` rather than `[x]`, and the reviewer should
  rule on it.** The `APIResponseValidationError` clause was written and then
  removed. Reaching it through the `httpx.MockTransport` seam proved impossible:
  the SDK accepts a run-create body of any shape, so no test would fail without
  the clause, and AGENT.md §5 forbids shipping code no test would fail without.

  Writing that test found a nearer defect instead, which is what shipped. A 2xx
  the SDK accepts but that carries no `run_id` makes
  `task_run.result(None)` raise a bare `ValueError` from inside the SDK, which
  `routes.py` maps to 500. `_find` now checks `run.run_id` and raises
  `ResearchUnavailable`, and the test fails without it. The original clause's
  risk is therefore narrower than written and still open: an
  `APIResponseValidationError` from the result call would still reach a 500.
  Recording it here rather than shipping untestable breadth.

  **Reviewed 2026-09-05 — CHANGES_REQUESTED (1 blocking).** Gates green:
  `./.claude/init.sh check` 7 passed, 0 failed (564 passed, 14 deselected).
  Criteria 1, 2, 3, 4, 6 and 7 verified against the code, not the block: the
  three `try`/`except` sites exist, each new test asserts the new subclass and
  so fails without it, and `tests/unit/test_error_boundaries.py`'s walk
  classifies the three new classes automatically.

  **Ruling on the `[~]`.** The criterion is unsatisfiable as written, and for a
  stronger reason than the implementer gave. `APIResponseValidationError` is
  not merely untestable through `httpx.MockTransport` — it is unreachable in
  production. The SDK raises it in exactly two places:
  `parallel/_response.py:253`, behind `if self._client._strict_response_validation`,
  and `parallel/_base_client.py:657`, on a `pydantic.ValidationError` out of
  `construct_type`, which is documented as loose coercion that returns a
  non-matching value as-is. `research.py:100` constructs `Parallel(...)`
  without `_strict_response_validation`, whose default is `False`
  (`parallel/_client.py:100`). Catching it would be dead code. Do not ship the
  clause; the leader should rewrite this criterion rather than have anyone
  satisfy it.

  **Blocking: `src/clearcut/adapters/parallel/research.py:116` — the
  substitution does not meet the criterion's intent.** Loose construction is
  precisely why a malformed 2xx arrives as a raw `str`, `list` or `None`
  instead of a `TaskRun`, so `run.run_id` — the guard itself — raises
  `AttributeError`, which `routes.py:106` maps to 500. Verified against the
  installed SDK through the seam already in the test file: a run-create
  answering 200 `[1, 2]` gives `AttributeError: 'list' object has no attribute
  'run_id'`, and one answering 200 `text/plain` with a non-JSON body gives
  `'str' object has no attribute 'run_id'`. The second is the realistic one — a
  proxy or WAF interstitial served as 200 text. The same class sits at
  `research.py:133`: `_first_cited_claim` reads `result.output`, which raises
  `AttributeError` on the same shapes.

  Required change: guard on the constructed type, not on the attribute, at both
  call sites — reject a `run` that is not a `TaskRun` and a `result` that is not
  a `TaskRunResult`, raising `ResearchUnavailable` — and add one test per site
  driving a 200 whose body the SDK cannot construct (a `text/plain` non-JSON
  body is enough for both), asserting `ResearchUnavailable` and that no
  `AttributeError` escapes. Both fail against the current code.

  Non-blocking, for the leader: criterion 5's text still names
  `APIResponseValidationError` and asserts it "currently escapes to a 500". It
  cannot arise at all under a non-strict client. Rewrite it to name the
  reachable defect — a 2xx the SDK cannot construct must cross the port as
  `ResearchUnavailable` — so the next attempt is not judged against a false
  premise.

  `./.claude/init.sh check` was run twice. The first run was red (5 passed, 2
  failed) on `web/src/features/tracker/TrackerRow.test.tsx` failing to resolve
  `./TrackerRow`; `web/src/features/tracker/` was being written concurrently by
  other work and is untracked. The re-run is the green one above. CP-056
  touches no `web/` file, so that transient is not this checkpoint's.

### CP-057 — Seed the demo project's bible facts through infrastructure
- Status: IN_REVIEW
- Attempts: 0/3
- Depth: 0
- Layer: infra
- Depends on: CP-055
- Acceptance:
  - [x] An infra script indexes the SDD section 8(d) bible fact into the real
        BigQuery lore table for the demo project, by calling
        `BigQueryLoreStore.index()` rather than repeating its schema.
  - [x] `--dry-run` prints what it would index and connects to nothing, so it
        runs on a machine with no credentials. One test asserts that.
  - [x] Failure path: a missing credential exits naming that variable, the
        same shape `provision_tracker_schema.py` already uses.
  - [~] After it runs, a project-scoped search returns the seeded fact, which
        is SDD section 8(b)'s check from inside our own code path.
  - [x] Gate: pytest, ruff, ruff format, `mypy src tests infra main.py`.
- Files: `infra/seed_project_bible.py`, `tests/unit/infra/test_seed_project_bible.py`,
  `infra/README.md`
- Notes: ADR 0011 rules this in as infrastructure rather than as
  `POST /api/projects/{id}/bible`, which stays MISSING and which the SDD keeps
  reporting as MISSING. The endpoint is a route plus a use case plus tests; this
  reaches the state section 8(d) needs in an hour. It is a real product gap: a
  producer cannot upload a bible in the demo, the facts are already there.

  **Implemented 2026-09-03.** Eight tests, watched failing first. Two are worth
  naming. One asserts the seeded fact is the *same object* as
  `scenario.BIBLE_FACT` rather than merely equal to it, because a copied string
  passes an equality check and still drifts the day someone edits the scenario.
  The other greps the script for the words that would remove rows, since
  `LoreStore` has no such method and a script appearing to offer one would be
  lying about what it can do.

  **The last criterion is `[~]`, blocked rather than skipped.** Confirming a
  project-scoped search returns the seeded fact needs the script to actually
  run, and that needs Application Default Credentials, which do not exist on
  this machine. `gcloud auth application-default login` is an interactive
  browser flow no agent can complete. Until then the script is proven against a
  recording fake and unproven against BigQuery, which is precisely the
  distinction D66 exists to keep visible.

  **Reconciled 2026-09-03 (leader).** ADC exists now, so that is no longer why
  the last criterion is `[~]`. `tests/live/test_bigquery_lore_store_live.py`
  proves a scratch-id fact round-trips through `lore_vectors`; it does not
  prove `infra/seed_project_bible.py` indexed `scenario.BIBLE_FACT` for
  `demo-project`. The reviewer either runs the script and a project-scoped
  search, or sends this back. Do not treat the scratch-id test as a substitute.

  A claim in the docstring was wrong and is corrected: the dry run does *not*
  need the project interpreter. `lore_store.py` and `scenario.py` reach no
  further than the stdlib-only domain layer, so a bare `python3` runs it. Only
  a real run, which imports langchain, needs the venv.

### CP-058 — Export traces to Grafana Cloud and see the five stage spans
- Status: BLOCKED
- Attempts: 0/3
- Depth: 0
- Layer: adapters
- Depends on: CP-055
- Acceptance:
  - [x] A Grafana Cloud stack exists and `OTEL_EXPORTER_OTLP_ENDPOINT` and
        `OTEL_EXPORTER_OTLP_HEADERS` are set, so `composition.py`'s exporters
        are built rather than returning `None`.
  - [ ] One live analyze run produces a trace in Grafana carrying all five
        stage spans (`ingest`, `extract`, `ground`, `research`, `track`) under
        one trace id. Today `test_observability.py` proves this in mock mode
        only; no test has ever proven it for the live adapters, because none
        runs them together.
  - [ ] `clearcut_gemini_tokens_total` shows non-zero prompt tokens for
        `gemini-3.7-flash`. A zero means the metric came from mock mode.
  - [ ] The four panels `infrastructure.md` section 10 names exist: stage
        latency, tokens per model, findings by severity, tracker items by
        state.
  - [x] Failure path: with the endpoint unset the app still starts and still
        serves, exporting nowhere. `test_composition.py:187` already proves
        this and must stay green.
- Files: `infra/grafana_dashboard.json`,
  `infra/provision_grafana_dashboard.py`,
  `tests/unit/infra/test_provision_grafana_dashboard.py`,
  `tests/live/test_grafana_receipt_live.py`,
  `docs/plan/infrastructure.md`, `infra/README.md`
- Notes: SDD section 8(d) asserts against this dashboard, so CP-059 cannot pass
  without it. The three uninstrumented adapters stay uninstrumented here:
  `ContinuityCheck`, `LoreStore` and `Notifier` emit neither span nor metric,
  so the waterfall will under-account for wall-clock latency. That is recorded
  in SDD section 6 and deferred by ADR 0011, not fixed in this checkpoint.

  **Reconciled 2026-09-03 (leader).** Criterion 1 holds: `.env` has both OTLP
  variables, pointing at `otlp-gateway-prod-sa-east-1.grafana.net`. Criterion 5
  holds: `test_composition.py:187` still proves the unset-endpoint path.
  Status stays IN_PROGRESS because the dashboard is still MISSING (SDD §6).

  Remaining:
  - the four panels `infrastructure.md` §10 names;
  - one live analyze whose five stage spans share one trace id *in Grafana*,
    not only in an in-memory exporter;
  - `clearcut_gemini_tokens_total` non-zero on that dashboard.

  `tests/live/test_end_to_end_live.py` already asserts the five spans and the
  token counter in-process. Its docstring records that a successful OTLP flush
  is not proof of receipt. Do not treat that test as this checkpoint. Do not
  instrument ContinuityCheck, LoreStore, or Notifier.

  **Implementer 2026-09-03.** Dashboard JSON and provision script are in
  `infra/`. Unit tests prove the four panels query
  `clearcut_stage_latency_ms`, `clearcut_gemini_tokens_total`,
  `clearcut_findings_total`, `clearcut_tracker_items`, that `--dry-run`
  prints them without connecting, and that a missing credential exits naming
  that variable. The live tests skip without `GRAFANA_URL` and
  `GRAFANA_TOKEN`. Criteria 2-4 stay unticked: a JSON file is not a Grafana
  dashboard.

  Tried, without printing secrets: `.env` and Secret Manager hold only the
  OTLP pair; Cloud Run env is the same set. The OTLP header is Basic
  `instanceId:glc_...`. That token authenticates to
  `https://grafana.com/api/instances` and lists zero stacks.
  `GET /api/hosted-metrics/<otlp-instance-id>` is 403. The OTLP gateway host
  is regional (`otlp-gateway-prod-sa-east-1.grafana.net`); Prometheus and
  Tempo query hosts are cluster-specific and not derivable from it. Grafana's
  dashboard and datasource-proxy APIs need the stack URL
  (`https://<slug>.grafana.net`) and a Grafana service account token
  (`glsa_...`), not the OTLP write token.

  Human action: in the Grafana Cloud stack, create a service account with
  dashboards:write plus datasource query, then set `GRAFANA_URL` and
  `GRAFANA_TOKEN`. Run
  `.venv/bin/python infra/provision_grafana_dashboard.py` and
  `pytest -m live tests/live/test_grafana_receipt_live.py`. Do not reuse the
  OTLP pair as `GRAFANA_TOKEN`.

  **Leader 2026-09-03 (D73).** Stop for a human (AGENT.md §6 B). Not
  superseded: the checkpoint is not too large; the obstacle is an external
  credential no agent can mint. Status stays BLOCKED. Needed: `GRAFANA_URL`
  (`https://<slug>.grafana.net`) and `GRAFANA_TOKEN` (`glsa_`, dashboards:write
  plus datasource query). The OTLP pair is the wrong credential. After those
  two vars exist, run the provision script and the live receipt test above.

### CP-059 — Run SDD section 8(d) against live services
- Status: TODO
- Attempts: 0/3
- Depth: 0
- Layer: tests
- Depends on: CP-055, CP-056, CP-057, CP-058
- Acceptance:
  - [x] A planted screenplay PDF in `gs://clearcut-scripts-intake` contains a
        Ferrari Testarossa (BRAND), "Hotel California" on a radio
        (MUSIC_EXISTING), and one contradiction of the fact CP-057 seeded
        (CONTINUITY).
  - [ ] One live analyze call surfaces all three findings with correct page
        numbers, asserted against the page numbers printed on the PDF.
  - [ ] The tracker reads exactly three open items at `BLOCKED`.
  - [ ] The run produced a Grafana trace with the five stage spans and
        non-zero token metrics.
  - [ ] The whole check runs under `@pytest.mark.live` and skips without
        credentials, so it can never pass by exercising the demo adapters.
  - [ ] Gate: `./.claude/init.sh live` green with credentials present.
- Files: `tests/live/test_end_to_end_live.py`, a planted PDF fixture
- Notes: This is the submission's evidence and the thing
  `infrastructure.md` section 11 means by "runtime proof that calls are real
  and not mocked". It closes SDD phases 1 through 4 at once, because each of
  their exit criteria is a subset of this one.

  The same three assertions already run in mock mode as a criterion on CP-043.
  That proved the wiring. This proves the services, and the Backlog entry that
  has said so since 2026-08-31 is finally promoted.

  **Reconciled 2026-09-03 (leader).** The test file is committed at `f8c12d0`
  and implements every criterion except Grafana receipt, which it puts out of
  band ("OTLP failures over HTTP are silent"). It has no pycache: it has never
  been collected. Status stays TODO because this block Depends on CP-058,
  which is not DONE.

  The planted PDF exists at `gs://clearcut-scripts-intake/demo-project/v1.pdf`
  (listed, not re-parsed). Two env gaps will skip the test when CP-058 lands:
  `NOTIFY_WEBHOOK_URL` is empty in `.env` (`composition._required_env` refuses
  to start without it — a human picks the URL), and
  `CLEARCUT_LIVE_SCRIPT_GCS_URI` is absent (a test input, not an app setting;
  point it at that PDF).

### CP-060 — Build the image and deploy it to Cloud Run
- Status: DONE
- Attempts: 0/3
- Depth: 0
- Layer: infra
- Depends on: CP-055
- Acceptance:
  - [x] Cloud Build built the image; local Docker was never needed, because
        `gcloud run deploy --source .` builds remotely. The Dockerfile exists
        and its seven static tests pass.
  - [x] The built image contains `web/dist`. A container run locally serves the
        SPA at `/`, which is the only proof the in-image `npm run build`
        actually ran.
  - [x] `gcloud run deploy` puts service `clearcut` in `us-central1` behind a
        public URL, with `--set-secrets` resolving through
        `roles/secretmanager.secretAccessor` and both `OTEL_EXPORTER_OTLP_*`
        variables mounted.
  - [x] `GET /api/health` on that URL reports `live`, not `mock`. A deployment
        that silently serves the demo scenario is the failure this criterion
        exists to catch.
  - [x] Failure path: a revision missing a required variable fails at startup
        naming it, rather than serving and 500ing on the first request.
        `composition.py:176` already does this; the reviewer ruled (2026-09-05)
        that the ten parametrized cases in
        `tests/unit/test_composition.py:476` plus
        `tests/unit/test_entrypoint.py:51` close this at the level this
        checkpoint operates at. No second, deliberately broken deploy.
- Files: `Dockerfile` if the build reveals a problem,
  `docs/plan/infrastructure.md` section 9
- Notes: The `CMD` is already proven without an image: gunicorn loaded
  `main:app`, `/api/health` returned `{"mode":"mock"}` at 200, and `/` served
  the SPA at 200. What is unproven is the build itself, and the two most
  likely failures are the buildpack fallback and `.gcloudignore` excluding
  something the build needs.

  **Reconciled 2026-09-03 (leader).** Service `clearcut` is live in
  `us-central1` as revision `clearcut-00005-sqx` at
  `https://clearcut-eflcclvn7a-uc.a.run.app`. The REST rename (D72) is that
  revision. The Notes above about an unproven build are stale. Status stays
  IN_REVIEW. The remaining `[~]` is the missing-variable startup path on a
  *deployed* revision; do not widen into a second deploy unless the reviewer
  requires it. `NOTIFY_WEBHOOK_URL` is empty locally; if that revision serves
  `live`, the secret is set there even though `.env` is not.

  **Reviewed 2026-09-05 — PASS, 0 blocking.** Verified, not assumed:
  `GET https://clearcut-eflcclvn7a-uc.a.run.app/api/health` -> 200
  `{"mode":"live"}`; `GET /` -> 200 serving the built SPA, whose
  `/assets/index-DJ387NV1.js` and `/assets/index-DhF37qvF.css` are Vite output
  hashes, so `web/dist` is in the image (criteria 1, 2, 4).
  `gcloud run services describe` reports `clearcut-00005-sqx` ready and serving
  in `us-central1`, with `PARALLEL_API_KEY`, `CLICKHOUSE_*`, `NOTIFY_WEBHOOK_URL`
  and both `OTEL_EXPORTER_OTLP_ENDPOINT` / `OTEL_EXPORTER_OTLP_HEADERS` mounted
  through `secretKeyRef`; a ready revision means the accessor role resolves
  (criterion 3). `./.claude/init.sh check` -> 7 passed, 0 failed
  (564 passed / 14 deselected, web 185 passed). `live` not run: a concurrent
  reviewer held the tier, and this checkpoint changes no adapter.

  **Ruling on the fifth criterion: the second deploy is not required.** The
  behaviour it names is entirely ours and entirely covered.
  `_required_env` raises inside `create_app()`, `main.py` binds `app` at import,
  and `test_import_builds_a_flask_app_with_no_socket_opened` proves that
  binding — so `gunicorn main:app` cannot reach a listening state with a
  variable missing. The ten parametrized cases of
  `test_live_wiring_fails_at_startup_naming_a_missing_required_variable` cover
  every required variable and match on its name, so deleting the raise fails
  ten tests. What a sixth, deliberately broken revision would add is Cloud Run's
  own contract — a container whose process exits at start is not routed traffic
  — which is the platform's documented behaviour, not ClearCut code. Its
  assertion would be on a GCP error string. Section 5's live tier exists to
  prove our adapters reached a real service, not to re-test the provider, and
  Section 4 forbids ceremony that proves nothing new. Against that, the cost is
  real: mutating a service other checkpoints and a running live tier depend on.
  All five revisions in the service's history deployed successfully, so no
  existing failure evidence could be read instead.

  Non-blocking, for the leader: `_LIVE_ENV_VALUES` (`tests/unit/test_composition.py:255`)
  is hand-maintained and currently matches the ten `_required_env` calls in
  `composition.py`, but nothing enforces that. An eleventh required variable
  would silently drop out of the parametrized failure coverage.
### CP-061 — Add the three domain values the API partition needs
- Status: DONE
- Attempts: 0/3
- Depth: 0
- Layer: domain
- Depends on: -
- Acceptance:
  - [x] `tests/unit/domain/test_project.py`: a frozen `Project(project_id,
        title, jurisdiction_code, created_at)` keeps the four values it was
        given, and two `Project`s with equal fields compare equal.
  - [x] Failure paths in the same file: a blank `project_id` raises
        `ValueError`, a blank `title` raises `ValueError`, and an unknown
        jurisdiction code raises the error `jurisdiction_for` already raises —
        validation happens in the constructor, so no caller can hold an invalid
        `Project`.
  - [x] `tests/unit/domain/test_bible.py`: `next_fact_number([])` is 1;
        `FACT-001` and `FACT-002` give 3; a gap (`FACT-001`, `FACT-003`) gives
        4; an id that does not match `^FACT-(\d+)$` is ignored rather than
        crashing. It mirrors `_next_evt_number`
        (`application/evaluate_delta.py:97-103`) without importing it.
  - [x] `tests/unit/domain/test_tracker.py`: `clearance_rollup(items)` returns
        a `ClearanceRollup(blocked, in_progress, cleared, needs_review)` whose
        counts sum to `total`, and whose `clearance_percent` weights each state
        0 / 50 / 100. Boundaries, each its own test: empty → 0; all BLOCKED →
        0; all CLEARED → 100; one item in each of the four states → 50;
        `[BLOCKED, IN_PROGRESS]` → 25; a halved percentage rounds up and the
        result is an `int`.
  - [x] `tests/unit/test_layer_boundaries.py` still passes: all three modules
        import stdlib and `clearcut.domain` only.
  - [x] Gate: `./.claude/init.sh check`.
- Files: `src/clearcut/domain/project.py`, `src/clearcut/domain/bible.py`,
  `src/clearcut/domain/tracker.py`, `tests/unit/domain/test_project.py`,
  `tests/unit/domain/test_bible.py`, `tests/unit/domain/test_tracker.py`
- Notes: No live test — this is the domain layer and touches no adapter (§5).
  `ProjectBible` gets its first consumer in CP-074; `ClearanceRollup` gets one
  in CP-071. Both are collected here so those two checkpoints stay inside one
  layer each. `clearance_rollup` buckets an item by `needs_review` ahead of
  `state` (weight 50, same as `IN_PROGRESS`) so the four buckets stay disjoint
  and sum to `total`; this worktree's `.venv` had to be rebuilt from
  `python@3.13` because the pre-existing one was an empty shell on a broken
  `python@3.14` (`pyexpat` ABI mismatch against the system `libexpat`, so
  `pip` itself could not bootstrap) — a machine-level defect unrelated to this
  checkpoint, fixed by using a working interpreter rather than the system one.

### CP-062 — Split the ClickHouse adapter into a package, changing no behaviour
- Status: IN_REVIEW
- Attempts: 0/3
- Depth: 0
- Layer: adapters
- Depends on: -
- Acceptance:
  - [x] `adapters/clickhouse/tracker.py` (308 lines) becomes `client.py` (the
        `_ChClient` protocol and `ClickHouseUnavailable`), `schema.py` (`DDL`
        and `ensure_schema`) and `tracker.py` (the store). Every name keeps its
        spelling, `TrackerItemNotFound` included —
        `tests/unit/test_error_boundaries.py:34` names it.
  - [x] The three import sites move with it: `composition.py`,
        `infra/provision_tracker_schema.py`,
        `tests/live/test_clickhouse_tracker_live.py`. `rg "clickhouse.tracker"`
        finds no stale path.
  - [x] `tests/unit/adapters/test_clickhouse_tracker.py` passes with only its
        import lines changed. No assertion is edited, because no behaviour
        changed — that is this checkpoint's whole invariant.
  - [x] `tests/unit/test_error_boundaries.py` still walks every adapter
        exception to exactly one domain error type.
  - [~] Live: `./.claude/init.sh live` still green, and
        `tests/live/test_clickhouse_tracker_live.py` still asserts what it
        asserted before against the real ClickHouse Cloud service. It runs
        through the moved `_ChClient` import, which is the only proof the split
        did not break the wiring the unit tests fake. This worktree has no
        `.env`, so `init.sh live` ran green with the three tracker-live tests
        *skipped*, not executed — proving only that the moved import collects
        cleanly, not that the real service still round-trips. Needs a run with
        credentials before this box is fully earned.
  - [x] Gate: `./.claude/init.sh check`.
- Files: `src/clearcut/adapters/clickhouse/{client.py,schema.py,tracker.py}`,
  `src/clearcut/composition.py`, `infra/provision_tracker_schema.py`,
  `tests/unit/adapters/test_clickhouse_tracker.py`,
  `tests/live/test_clickhouse_tracker_live.py`
- Notes: Mechanical, and deliberately alone. CP-063 changes the DDL and the
  keys; doing both in one turn would make a data-integrity fix (D77) arrive
  inside a 300-line move, where a reviewer cannot see it.

  **Implementer 2026-09-04.** Two decisions the acceptance text left implicit:

  1. `ClickHouseUnavailable` replaces `TrackerUnavailable` (the class moves to
     `client.py` under the name the checkpoint text already uses for it, and
     which CP-063/CP-064 both assume exists there). That rename reaches one
     file the "Files" list above does not name:
     `tests/unit/adapters/test_error_translation.py` (import line and one
     `raise` site only, same "no assertion edited" invariant `Files` already
     holds the rest of the diff to). Flagging it explicitly since it is a
     deviation from the stated file set, not an omission.
  2. `tests/unit/test_layer_boundaries.py::test_composition_is_the_only_module_
     importing_adapters` only exempts a same-package import shaped
     `from clearcut.adapters.<pkg> import <sibling>` (package-level, matching
     `adapters/demo/in_memory.py`'s existing `from clearcut.adapters.demo
     import scenario`) — not `from clearcut.adapters.<pkg>.<sibling> import
     X`. `tracker.py` and `schema.py` therefore import `client`/`schema` as
     modules (`ch_client._ChClient`, `ch_client.ClickHouseUnavailable`,
     `schema.ensure_schema`) rather than importing names directly, or the
     layer gate fails. This is worth a Backlog note if a future split ever
     wants the direct-name-import ergonomics back — it would need the gate
     widened first.

  Live tier: this worktree carries no ClickHouse credentials, so
  `./.claude/init.sh live` passed with the three
  `test_clickhouse_tracker_live.py` cases **skipped**, not run — the
  acceptance box above is left `[~]` rather than checked. `./.claude/init.sh
  check` (7/7, including `pytest -q` at 558 passed) is the gate this turn
  actually cleared.

  **Reviewer 2026-09-04 — unit review passed, live run still pending.** Status
  stays `IN_REVIEW` and `Attempts` stays `0/3`: every criterion except the live
  box is met, and the live box cannot be judged in this worktree, which carries
  no `.env` by design. Zero blocking findings. Evidence, re-run rather than
  taken from the turn above: `./.claude/init.sh check` 7 passed / 0 failed
  (`ruff check`, `ruff format`, `mypy`, `pytest -q` 558 passed / 11 deselected,
  `web lint:css`, `web typecheck`, `web test` 64 passed);
  `./.claude/init.sh live` 1 passed with 11 live cases skipped, three of them
  `test_clickhouse_tracker_live.py`, each naming the credentials it lacks — the
  honest outcome for a live test without credentials, and not a pass.

  The no-behaviour-change invariant holds mechanically. Both DDL strings are
  byte-identical to `974c5b1`'s. The old 308-line module's def/class set is
  preserved across the new 42 + 60 + 246 lines, the only differences being the
  `TrackerUnavailable` → `ClickHouseUnavailable` rename and
  `schema.ensure_schema` as a module-level function beside the store method that
  now delegates to it. `git diff 974c5b1 1dc252d --
  tests/unit/adapters/test_clickhouse_tracker.py` is import lines plus five
  `pytest.raises` type names carrying that rename; no arranged input, no
  expected value and no other assertion is touched.
  `tests/unit/test_error_boundaries.py` still walks the package with
  `pkgutil.walk_packages`, so `client.py` is inspected automatically and
  `ClickHouseUnavailable` would fail that walk if it did not subclass exactly
  one domain error.

  Both implementer judgment calls are accepted, on the record:

  1. **The rename, and the file outside `Files`.** The acceptance text's own
     first clause names `ClickHouseUnavailable` as what `client.py` holds, and
     CP-063 and CP-064 both assert a client error becomes that type. "Every name
     keeps its spelling" is qualified by the parenthetical naming
     `TrackerItemNotFound`, which is the name `test_error_boundaries.py` pins.
     Keeping `TrackerUnavailable` would have contradicted the criterion it sits
     in and pushed the rename into CP-063, where it would land inside a DDL and
     key change — the exact mixing this checkpoint's Notes exist to prevent. The
     reach into `tests/unit/adapters/test_error_translation.py` is one import
     line and one `raise` argument; its assertion,
     `pytest.raises(SourceUnavailable)`, is unchanged. Declaring it in Notes was
     the right handling.
  2. **Module-shaped sibling imports.** Verified against the gate rather than
     accepted on assertion: `_adapter_import_violations` allows an adapters
     import only when the imported name equals the module's own package, so
     `from clearcut.adapters.clickhouse.client import X` inside the package
     would be reported as `clearcut.adapters.clickhouse.client` and fail, while
     `from clearcut.adapters.clickhouse import client as ch_client` matches the
     package exactly and passes. The chosen shape is the only one the existing
     gate permits, and it adds no indirection of its own.

  No Section 4 finding. `schema.ensure_schema` and the `DDL` tuple are named by
  the acceptance criteria and consumed by CP-063, which depends on this
  checkpoint, so they are a move under a stated requirement rather than a
  speculative abstraction. No secrets in the diff; no `.env` was created or
  copied. `rg "clickhouse.tracker"` returns only live references to the module
  that still exists.

  One non-blocking observation, deliberately not filed as its own checkpoint
  because CP-063 already edits the file: five test functions in
  `tests/unit/adapters/test_clickhouse_tracker.py` still read
  `..._wraps_a_client_error_as_tracker_unavailable` while raising
  `ClickHouseUnavailable`. Renaming them here would have widened the diff past
  the invariant this checkpoint is built on; CP-063 can refresh them in passing.

  What remains before `DONE`: one `./.claude/init.sh live` run with
  `CLICKHOUSE_HOST`, `CLICKHOUSE_USER` and `CLICKHOUSE_PASSWORD` present, so the
  three tracker cases execute against ClickHouse Cloud and the `[~]` box is
  earned. The conductor runs it where those credentials exist.

### CP-063 — Give the script aggregate its own store, keyed so versions survive
- Status: TODO
- Attempts: 0/3
- Depth: 0
- Layer: adapters
- Depends on: CP-062
- Acceptance:
  - [ ] `application/ports.py` declares `ScriptStore` with `record`, `latest`,
        `list_for_project`, `get` (raising `RecordNotFound` when absent),
        `record_findings` and `findings_for`. `TrackerStore` no longer declares
        `record_script` or `latest_script`; `latest(item_id)` is unchanged
        here, and CP-070 changes it.
  - [ ] `tests/unit/application/test_ports.py` binds `FakeScriptStore` to
        `ScriptStore` through an annotated assignment made *before* any
        `isinstance` narrowing — the inert-binding pitfall D3 records.
  - [ ] `DDL` in `schema.py` creates `script_versions` as
        `ReplacingMergeTree ORDER BY (project_id, script_id)` with no
        `(version)` argument, `findings` as `ReplacingMergeTree ORDER BY
        (script_id, finding_id)` with citations in a JSON column, and
        `tracker_items` as `ReplacingMergeTree(version) ORDER BY (project_id,
        item_id)`. A test asserts each engine line, because these three strings
        are the defect D77 describes.
  - [ ] `tests/unit/adapters/test_clickhouse_scripts.py`: `record` then
        `get(project_id, script_id)` round-trips a `Script` with its scenes;
        `list_for_project` returns versions ascending; `latest` picks the
        maximum version client-side; `findings_for` returns what
        `record_findings` stored, citations included.
  - [ ] Failure paths in that file: `get` on an unknown `script_id` raises
        `RecordNotFound`, and a client error becomes `ClickHouseUnavailable`,
        not the driver's exception.
  - [ ] `AnalyzeScript` and `EvaluateDelta` take `scripts: ScriptStore` (eight
        and nine parameters, D78) and call it instead of the tracker's script
        methods. Their existing tests pass with the new fake wired in.
  - [ ] `InMemoryScriptStore` in `adapters/demo/in_memory.py`, seeded with the
        scenario script, and `composition.py` wires one instance into both
        modes. `tests/unit/test_composition.py` asserts both builders share it.
  - [ ] Live: new `tests/live/test_clickhouse_scripts_live.py` records v1 and
        v2 of one project's script into the real service, runs `OPTIMIZE TABLE
        script_versions FINAL` to force the merge, and asserts
        `list_for_project` returns **both** rows and `get` returns v1's scenes.
        Against today's `ReplacingMergeTree(version) ORDER BY project_id` the
        merge deletes v1 and this test fails; no fake can fail it.
  - [ ] Live: `tests/live/test_clickhouse_tracker_live.py` gains an assertion
        that `EVT-001` saved under two different project ids leaves two rows
        after `OPTIMIZE TABLE tracker_items FINAL`. That is the key fix itself.
  - [ ] Gate: `./.claude/init.sh check` and `./.claude/init.sh live`.
- Files: `src/clearcut/application/ports.py`,
  `src/clearcut/application/{analyze_script.py,evaluate_delta.py}`,
  `src/clearcut/adapters/clickhouse/{schema.py,scripts.py,tracker.py}`,
  `src/clearcut/adapters/demo/in_memory.py`, `src/clearcut/composition.py`,
  `tests/unit/fakes.py`, `tests/unit/application/test_ports.py`,
  `tests/unit/application/{test_analyze_script.py,test_evaluate_delta.py}`,
  `tests/unit/adapters/test_clickhouse_scripts.py`,
  `tests/unit/test_composition.py`,
  `tests/live/{test_clickhouse_scripts_live.py,test_clickhouse_tracker_live.py}`
- Notes: The live tests need the new tables, so provision them against a scratch
  database first — CP-067 builds the `--recreate` path for the deployed ones and
  CP-077 executes it after the human confirms. Do not run a DROP against the
  demo tables here.

### CP-064 — Persist projects, so a producer can create one
- Status: TODO
- Attempts: 0/3
- Depth: 0
- Layer: adapters
- Depends on: CP-061, CP-063
- Acceptance:
  - [ ] `ProjectStore` in `ports.py` with `save`, `get` (raising
        `RecordNotFound`) and `list`, bound to `FakeProjectStore` in
        `tests/unit/application/test_ports.py`.
  - [ ] `DDL` gains `projects` as `ReplacingMergeTree ORDER BY project_id`.
  - [ ] `tests/unit/adapters/test_clickhouse_projects.py`: `save` then `get`
        round-trips all four `Project` fields; `list` returns every saved
        project; `get` on an unknown id raises `RecordNotFound`; a client error
        becomes `ClickHouseUnavailable`.
  - [ ] `InMemoryProjectStore` seeded with a new `scenario.PROJECT =
        Project("demo-project", ..., "AR", ...)`, so mock mode lists the same
        project its tracker and script already describe.
        `tests/unit/adapters/test_demo_scenario.py` asserts the seeded id
        matches the scenario's tracker items.
  - [ ] `composition.py` builds `ClickHouseProjectStore` in live mode and the
        in-memory one in mock mode, sharing the single client the other stores
        use; `tests/unit/test_composition.py` asserts that.
  - [ ] Live: new `tests/live/test_clickhouse_projects_live.py` saves a project
        with a scratch id and a microsecond-precision `created_at`, reads it
        back with `get`, and asserts the `created_at` the **server** returned
        equals what ClickHouse's `DateTime64` actually stores. A fake returns
        the object it was handed and cannot fail on the column's precision.
  - [ ] Gate: `./.claude/init.sh check` and `./.claude/init.sh live`.
- Files: `src/clearcut/application/ports.py`,
  `src/clearcut/adapters/clickhouse/{schema.py,projects.py}`,
  `src/clearcut/adapters/demo/{in_memory.py,scenario.py}`,
  `src/clearcut/composition.py`, `tests/unit/fakes.py`,
  `tests/unit/application/test_ports.py`,
  `tests/unit/adapters/{test_clickhouse_projects.py,test_demo_scenario.py}`,
  `tests/unit/test_composition.py`,
  `tests/live/test_clickhouse_projects_live.py`
- Notes: No HTTP route yet — CP-071 adds it. This checkpoint only makes a
  project a thing the system can store, which is what D75 reverses ADR 0011 to
  allow.

### CP-065 — Store an uploaded screenplay in the intake bucket
- Status: TODO
- Attempts: 0/3
- Depth: 0
- Layer: adapters
- Depends on: CP-064
- Acceptance:
  - [ ] `ScriptStorage` in `ports.py` — one method,
        `put(project_id, object_name, content) -> str` returning the `gs://`
        URI. It is a port because it crosses a real network boundary (§4);
        nothing else is added to it.
  - [ ] `adapters/gcp/storage.py` holds `GcsScriptStorage(client, bucket_name)`
        over narrow `_StorageClient` / `_Bucket` / `_Blob` protocols, matching
        how `document_ai.py` and `vertex_search.py` already type their clients.
  - [ ] `tests/unit/adapters/test_gcs_script_storage.py`: `put` uploads to
        `{project_id}/{object_name}` and returns
        `gs://{bucket}/{project_id}/{object_name}`; a `GoogleAPIError` from the
        client becomes `ScriptUploadFailed`, a `SourceUnavailable` subclass, so
        the route answers 502 rather than 500.
        `tests/unit/test_error_boundaries.py` covers it in the contract walk.
  - [ ] `google-cloud-storage==3.13.1` is declared in `pyproject.toml`;
        `tests/unit/test_declared_dependencies.py` passes, which it would not
        the moment the import lands undeclared.
  - [ ] `SCRIPTS_INTAKE_BUCKET` is read by `_required_env` in `composition.py`
        and appears in `.env.example`, `docs/plan/infrastructure.md` §8 and
        `tests/unit/test_composition.py::_LIVE_ENV_VALUES`.
        `tests/unit/test_environment_contract.py` is bidirectional and proves
        the documented set and the required set are the same set.
  - [ ] `InMemoryScriptStorage` returns
        `gs://clearcut-demo/{project_id}/{object_name}` so mock mode answers
        without a bucket.
  - [ ] Live: new `tests/live/test_gcs_script_storage_live.py` uploads bytes to
        the real `clearcut-scripts-intake` bucket under a scratch object name,
        re-fetches the blob through `bucket.get_blob`, and asserts
        `blob.size == len(content)` and a non-empty server-assigned
        `generation`. Both values come from GCS, not from the code under test.
        The test deletes the object afterwards.
  - [ ] Gate: `./.claude/init.sh check` and `./.claude/init.sh live`.
- Files: `src/clearcut/application/ports.py`,
  `src/clearcut/adapters/gcp/storage.py`,
  `src/clearcut/adapters/demo/in_memory.py`, `src/clearcut/composition.py`,
  `pyproject.toml`, `.env.example`, `docs/plan/infrastructure.md`,
  `tests/unit/fakes.py`, `tests/unit/application/test_ports.py`,
  `tests/unit/adapters/test_gcs_script_storage.py`,
  `tests/unit/{test_composition.py,test_error_boundaries.py}`,
  `tests/live/test_gcs_script_storage_live.py`
- Notes: The bucket already exists (`infra/provision_data_plane.sh:24`). D10
  deferred multipart upload behind exactly this port; this is that port, and
  CP-072 is the route above it. `google-cloud-storage` is installed
  transitively today, which is why the declared-dependency test is the
  criterion that matters.

### CP-066 — Read a project's bible facts back out of BigQuery
- Status: TODO
- Attempts: 0/3
- Depth: 0
- Layer: adapters
- Depends on: CP-065
- Acceptance:
  - [ ] `LoreStore` gains `facts(project_id) -> list[BibleFact]`. The port keeps
        three methods; nothing else is added.
  - [ ] `BigQueryLoreStore.facts` calls `get_documents(filter={"project_id":
        ..., "kind": "bible_fact"})` and reconstructs each `BibleFact` from
        stored metadata.
  - [ ] `index` writes `fact_id`, `fact_kind` and `source` into the metadata of
        a fact row, so a fact read back is the fact that was written rather
        than one reconstructed from its text.
  - [ ] `tests/unit/adapters/test_lore_store.py`: a row indexed before this
        change — no `fact_id` in its metadata — still returns a usable
        `BibleFact` through the documented fallback instead of raising
        `KeyError`. That is the failure path, and the demo project has such
        rows today.
  - [ ] The `_VectorStore` protocol and both of its test fakes gain
        `get_documents`; mypy passes over the annotated binding.
  - [ ] `InMemoryLoreStore.facts` returns the scenario's seeded facts, so mock
        mode serves a bible.
  - [ ] Live: `tests/live/test_bigquery_lore_store_live.py` indexes a fact
        under a scratch project id with a known `fact_id`, then asserts
        `facts(project_id)` returns a `BibleFact` carrying that same `fact_id`,
        `kind` and `source` **read back from BigQuery's stored metadata**. The
        existing search-based test cannot prove that: it matches on text, which
        a fake reproduces exactly.
  - [ ] Gate: `./.claude/init.sh check` and `./.claude/init.sh live`.
- Files: `src/clearcut/application/ports.py`,
  `src/clearcut/adapters/bigquery/lore_store.py`,
  `src/clearcut/adapters/demo/in_memory.py`, `tests/unit/fakes.py`,
  `tests/unit/application/test_ports.py`,
  `tests/unit/adapters/test_lore_store.py`,
  `tests/live/test_bigquery_lore_store_live.py`
- Notes: The demo project's existing lore rows lack `fact_id`, which is both why
  the fallback exists and why CP-077's runbook deletes them before re-seeding —
  re-seeding over them duplicates the demo fact.

### CP-067 — Let the infra scripts rebuild and reseed the four tables
- Status: TODO
- Attempts: 0/3
- Depth: 0
- Layer: infra
- Depends on: CP-064
- Acceptance:
  - [ ] `infra/provision_tracker_schema.py --recreate` drops and re-creates
        `tracker_items`, `script_versions`, `findings` and `projects`, in that
        order, from `schema.py`'s `DDL` rather than from statements repeated in
        the script. ClickHouse cannot alter `ORDER BY` in place, which is why
        this exists (D77).
  - [ ] It refuses to run unattended: `--recreate` prompts for a typed `yes`
        unless `--force` is also given.
        `tests/unit/infra/test_provision_tracker_schema.py` asserts a declined
        prompt executes no statement.
  - [ ] `--dry-run --recreate` prints eight statements (four DROP, four CREATE)
        and connects to nothing. One test asserts the count and that no client
        was constructed, so it runs on a machine with no credentials.
  - [ ] Failure path: a missing credential exits naming the variable, matching
        the shape the script already uses.
  - [ ] `infra/seed_project_bible.py` also saves `scenario.PROJECT` through
        `ProjectStore`, so a reseeded demo has a project row and not only
        facts. `tests/unit/infra/test_seed_project_bible.py` asserts the saved
        project is the scenario object itself, the same identity check CP-057
        used for the bible fact.
  - [ ] `infra/README.md` documents `--recreate` as destructive, names the four
        tables, and says the deployed service loses its tracker history.
  - [ ] Gate: `./.claude/init.sh check`.
- Files: `infra/provision_tracker_schema.py`, `infra/seed_project_bible.py`,
  `infra/README.md`,
  `tests/unit/infra/{test_provision_tracker_schema.py,test_seed_project_bible.py}`
- Notes: This checkpoint only builds the tool. Running it against the deployed
  service is CP-077, after the human confirms, because it destroys the demo
  tracker history. No live test: the script is infra, and the DDL it executes is
  already proved live by CP-063 and CP-064.

### CP-068 — Extract the HTTP helpers out of the one route module
- Status: TODO
- Attempts: 0/3
- Depth: 0
- Layer: adapters
- Depends on: CP-066, CP-067
- Acceptance:
  - [ ] `adapters/http/errors.py` holds `error_response` and
        `run_use_case(build, *, status=200, location_of=None)` with the
        404/502/500 mapping now inline at `routes.py:90-112`.
  - [ ] `adapters/http/validators.py` holds `json_body`, `require_field`,
        `require_version`, `require_state`, `resolve_jurisdiction`, `now` and
        `new_id` from `routes.py:77-136, 230-239`.
  - [ ] `adapters/http/serializers.py` holds the serializers with two or more
        consuming domains: citation, scene, finding, tracker item, analysis
        report, bible fact (`routes.py:151-219`).
  - [ ] `tests/unit/adapters/test_http_errors.py` covers the mapping directly:
        a `RecordNotFound` becomes 404, a `SourceUnavailable` becomes 502, an
        unexpected exception becomes 500 with no traceback in the body, and
        `location_of` sets the `Location` header on a 201.
  - [ ] `tests/unit/adapters/test_http_validators.py` covers each validator's
        failure: absent JSON body, missing field, non-integer version, unknown
        state, unknown jurisdiction code — each a 400 carrying the field name.
  - [ ] `tests/unit/adapters/http_support.py` holds the shared test builder the
        five route suites will use, so each domain suite constructs an app
        without repeating composition.
  - [ ] Invariant: `tests/unit/adapters/test_routes.py` passes with **no edited
        assertion**. `routes.py` shrinks to handlers plus its blueprint and
        imports the three new modules. No path, status code or response body
        changes.
  - [ ] Gate: `./.claude/init.sh check`.
- Files:
  `src/clearcut/adapters/http/{errors.py,validators.py,serializers.py,routes.py}`,
  `tests/unit/adapters/{http_support.py,test_http_errors.py,test_http_validators.py}`
- Notes: No live test (D83). The extraction is separated from the partition so
  that CP-069 is a move of whole handlers rather than a move plus a
  decomposition.

### CP-069 — Partition the HTTP adapter and the OpenAPI document by domain
- Status: TODO
- Attempts: 0/3
- Depth: 0
- Layer: adapters
- Depends on: CP-068
- Acceptance:
  - [ ] `adapters/http/schemas.py` holds `ref`, `json_of`, `json_array_of`,
        `path_param`, `error`, `INTERNAL_ERROR`, the `SHARED` schemas (`Error`,
        `Citation`, `Scene`, `Finding`, `TrackerItem`, `ScriptAnalysis`,
        `BibleFact`) and `merge_schemas`, which **raises** on a duplicate name
        rather than letting one domain silently overwrite another's schema. One
        test asserts that raise.
  - [ ] `adapters/http/openapi.py` holds `_INFO`, the Swagger HTML,
        `merge_paths` (raising on a duplicate `(path, method)`), `build_spec`
        over a `DOMAINS` tuple, and `create_openapi_blueprint`.
  - [ ] Today's operations move into `system.py` (health, openapi, docs),
        `scripts.py` (create), `tracker.py` (list, transition, actions) and
        `questions.py` (ask), each module exporting `create_<domain>_blueprint`,
        `TAG`, `PATHS` and `SCHEMAS`. `projects.py` and `bible.py` are **not**
        created empty; CP-071 and CP-074 add them with their first operation
        (§4).
  - [ ] `routes.py`, `docs.py` and `health.py` are deleted, with
        `test_routes.py`, `test_docs.py` and `test_health.py` replaced by
        `test_openapi.py`, `test_system.py` and one `test_<domain>_routes.py`
        per populated domain.
  - [ ] Drift test in `test_openapi.py`, both directions: every `(path, method)`
        Flask serves appears in the document, and every one the document
        declares is served. It fails if either side gains an entry alone.
  - [ ] Every operation carries exactly one tag naming its module, every
        `operationId` is unique across the document, every `$ref` resolves
        inside `components/schemas`, every operation documents a `500`
        referencing `Error`, and an array response is typed as an array — the
        tracker list is documented as an object today and returns a list.
  - [ ] Invariant: the served `(path, method)` set and every status code are
        unchanged from CP-068. `tests/unit/adapters/test_spa.py` still passes
        untouched, and so does the SPA catch-all rule
        (`composition.py:342-343`) — the openapi blueprint registers before it
        and the SPA blueprint stays last.
  - [ ] `tests/unit/test_entrypoint.py` asserts one registration rule per
        domain, and `tests/unit/test_layer_boundaries.py:214`'s planted path is
        updated to a module that still exists.
  - [ ] Gate: `./.claude/init.sh check`.
- Files:
  `src/clearcut/adapters/http/{schemas.py,openapi.py,system.py,scripts.py,tracker.py,questions.py}`,
  deletes `src/clearcut/adapters/http/{routes.py,docs.py,health.py}`,
  `src/clearcut/composition.py`,
  `tests/unit/adapters/{test_openapi.py,test_system.py,test_scripts_routes.py,test_tracker_routes.py,test_questions_routes.py}`,
  deletes `tests/unit/adapters/{test_routes.py,test_docs.py,test_health.py}`,
  `tests/unit/{test_entrypoint.py,test_layer_boundaries.py}`
- Notes: No live test (D83); CP-077 exercises the document against the deployed
  revision. The invariant is what makes this reviewable at its size: if any
  status code or path moved, the checkpoint did more than it claims. Four tags
  exist at the end of it, not six — CP-071 and CP-074 add the other two with
  their modules.

### CP-070 — Nest the tracker under its project and correct the write statuses
- Status: TODO
- Attempts: 0/3
- Depth: 0
- Layer: adapters
- Depends on: CP-069
- Acceptance:
  - [ ] `TrackerStore.latest(project_id, item_id)` is project-scoped, and
        `ClickHouseTrackerStore` filters `WHERE project_id = ... AND item_id =
        ...`. `InMemoryTrackerStore` is keyed by the pair. This is the read half
        of D77.
  - [ ] `ResolveFinding.execute(project_id, item_id, action, at)` passes the
        project through; `tests/unit/application/test_resolve_finding.py` proves
        two projects holding the same `EVT-001` resolve independently — with the
        old key one overwrites the other.
  - [ ] `PATCH /api/projects/{project_id}/tracker-items/{item_id}` replaces the
        top-level `PATCH /api/tracker-items/{item_id}`, which is gone: a request
        to the old path returns 404 from routing, not 400 from a handler.
  - [ ] `POST /api/projects/{project_id}/scripts` returns **201** with a
        `Location` header naming the created script, not 200. `test_spa.py` and
        `test_scripts_routes.py` assert the status and the header.
  - [ ] `question` is required: `POST .../questions` with a blank or absent
        `question` returns 400 and calls no adapter. A test asserts the fake was
        never called, so an empty question cannot reach Gemini.
  - [ ] `web/src/api/client.ts` `patchTrackerState` takes `projectId`, and
        `TrackerDashboard.tsx` passes it. The web typecheck and tests pass —
        `client.ts` stays the only file holding `/api/` literals.
  - [ ] Live: `tests/live/test_clickhouse_tracker_live.py` saves `EVT-001` under
        two different project ids, runs `OPTIMIZE TABLE tracker_items FINAL`,
        and asserts `latest("proj-a", "EVT-001")` and `latest("proj-b",
        "EVT-001")` each return their own project's item. Against the old key
        one row is deleted by the merge and the second call raises; no fake can
        reproduce a ClickHouse merge.
  - [ ] Gate: `./.claude/init.sh check` and `./.claude/init.sh live`.
- Files:
  `src/clearcut/application/{ports.py,resolve_finding.py,list_tracker_items.py}`,
  `src/clearcut/adapters/clickhouse/tracker.py`,
  `src/clearcut/adapters/demo/in_memory.py`,
  `src/clearcut/adapters/http/{tracker.py,scripts.py,questions.py}`,
  `tests/unit/fakes.py`, `tests/unit/application/test_resolve_finding.py`,
  `tests/unit/adapters/{test_tracker_routes.py,test_scripts_routes.py,test_questions_routes.py,test_spa.py}`,
  `tests/live/test_clickhouse_tracker_live.py`, `web/src/api/client.ts`,
  `web/src/components/organisms/TrackerDashboard.tsx`
- Notes: This is the behavioural half of the partition, and the checkpoint the
  whole data-integrity fix rests on. `POST .../actions` is untouched here — its
  removal belongs with the sub-resources that replace it (CP-073, D76).

### CP-071 — Serve projects and jurisdictions as resources
- Status: TODO
- Attempts: 0/3
- Depth: 0
- Layer: application
- Depends on: CP-070
- Acceptance:
  - [ ] `CreateProject(projects).execute(project_id, title, jurisdiction, at)`
        returns the saved `Project`; `summarize(project, tracker, scripts)` is a
        plain function returning `ProjectSummary(project, rollup,
        latest_script_version)`; `ListProjects(projects, tracker,
        scripts).execute()` returns summaries `created_at` descending;
        `GetProject(...).execute(project_id)` returns one.
  - [ ] Unit tests, one file per use case under `tests/unit/application/`:
        happy path plus a failure path each — `GetProject` on an unknown id
        raises `RecordNotFound`, `CreateProject` with a blank title propagates
        the domain `ValueError` rather than saving, and `ListProjects` returns
        `[]` rather than raising when no project exists.
  - [ ] `GET /api/projects` returns 200 and a JSON **array** of
        `ProjectSummary`; in mock mode it contains the seeded `demo-project`
        with `clearance_percent` 0, and 50 after one item moves to
        `IN_PROGRESS`. That second assertion is what proves the rollup is
        computed rather than stored.
  - [ ] `POST /api/projects` returns 201 with a `Location` header and the
        created `Project`, its id a `uuid4().hex`. Failure paths: a missing
        `title` → 400, an unknown `jurisdiction_code` → 400, and no store call
        in either case.
  - [ ] `GET /api/projects/{project_id}` returns 200, and 404 for an unknown id.
  - [ ] `GET /api/jurisdictions` returns the ten entries of
        `domain/jurisdiction.JURISDICTIONS` with no port involved — reading a
        domain constant is not I/O (§4).
  - [ ] `adapters/http/projects.py` is added to `DOMAINS` in `openapi.py` and
        registered in `composition.py`; the drift test in `test_openapi.py`
        passes with the four new operations, each tagged `Projects` with a
        unique `operationId`.
  - [ ] Gate: `./.claude/init.sh check`.
- Files:
  `src/clearcut/application/{create_project.py,project_summary.py,list_projects.py,get_project.py}`,
  `src/clearcut/adapters/http/{projects.py,openapi.py}`,
  `src/clearcut/composition.py`,
  `tests/unit/application/{test_create_project.py,test_project_summary.py,test_list_projects.py,test_get_project.py}`,
  `tests/unit/adapters/test_projects_routes.py`,
  `tests/unit/test_composition.py`
- Notes: Parallel with CP-072, CP-073, CP-074; shares only the additive lines in
  `composition.py`, `test_composition.py` and `openapi.py`'s `DOMAINS` (D81). No
  live test (D83). `ClearanceRollup` comes from CP-061, so no domain file is
  touched here.

### CP-072 — Accept a screenplay upload and serve script reads
- Status: TODO
- Attempts: 0/3
- Depth: 0
- Layer: application
- Depends on: CP-070
- Acceptance:
  - [ ] `UploadScriptFile(storage).execute(project_id, upload_id, file_name,
        content)` returns `StoredScriptFile(gcs_uri, file_name, size_bytes)`
        and stores the object as `{upload_id}.pdf`.
  - [ ] `ListScripts(scripts).execute(project_id)` returns versions ascending;
        `GetScript(scripts, tracker).execute(project_id, script_id)` returns an
        `AnalysisReport` whose tracker items are `latest_for_project` filtered
        to that script's finding ids.
  - [ ] Unit tests per use case with a failure path each: `GetScript` on an
        unknown id raises `RecordNotFound`, `ListScripts` returns `[]` for a
        project with no script, and `UploadScriptFile` propagates
        `ScriptUploadFailed` rather than swallowing it.
  - [ ] `POST /api/projects/{project_id}/script-files` accepts multipart `file`
        and returns 201 with the `gs://` URI. In mock mode
        `test_scripts_routes.py` asserts `gs://clearcut-demo/...`.
  - [ ] Failure paths on that route, each its own test: a non-PDF → 400, a file
        over 25 MiB → **413**, an absent `file` part → 400, and a storage
        outage → 502. The 25 MiB cap sits under Cloud Run's 32 MiB request
        limit, so the 413 is ours to return.
  - [ ] `GET /api/projects/{project_id}/scripts` returns 200 and an array of
        `ScriptSummary`.
  - [ ] `GET /api/projects/{project_id}/scripts/{script_id}` returns 200 with
        **the same eight top-level keys** its `POST` returns — one test compares
        the two key sets directly, so the two shapes cannot drift. An unknown
        `script_id` → 404.
  - [ ] The three operations join `scripts.py`'s `PATHS` and `SCHEMAS`; the
        drift test passes and every new `operationId` is unique. If `scripts.py`
        crosses 300 lines, its `PATHS`/`SCHEMAS` move to `scripts_spec.py` in
        the same package rather than the handlers being compressed.
  - [ ] Gate: `./.claude/init.sh check`.
- Files:
  `src/clearcut/application/{upload_script_file.py,list_scripts.py,get_script.py}`,
  `src/clearcut/adapters/http/scripts.py` (and `scripts_spec.py` if needed),
  `src/clearcut/composition.py`,
  `tests/unit/application/{test_upload_script_file.py,test_list_scripts.py,test_get_script.py}`,
  `tests/unit/adapters/test_scripts_routes.py`,
  `tests/unit/test_composition.py`
- Notes: The heaviest of the four parallel units — three use cases plus
  multipart handling. It is `Depth: 0`, so if it blocks it can still be split
  once, most naturally into upload and reads (D82). No live test (D83): the GCS
  adapter beneath it was proved live by CP-065. A v2 script's `GET` returns the
  delta's findings, matching its own `POST` (D80).

### CP-073 — Replace the tracker action verb with two sub-resources
- Status: TODO
- Attempts: 0/3
- Depth: 0
- Layer: application
- Depends on: CP-070
- Acceptance:
  - [ ] `GetTrackerItem(tracker).execute(project_id, item_id)` returns one item;
        `tests/unit/application/test_get_tracker_item.py` covers the happy path
        and `RecordNotFound` for an unknown id.
  - [ ] `GET /api/projects/{project_id}/tracker-items/{item_id}` returns 200,
        and 404 for an unknown item.
  - [ ] `POST .../tracker-items/{item_id}/email-drafts` returns 201 carrying the
        item with `draft_email` set; 404 for an unknown item.
  - [ ] `POST .../tracker-items/{item_id}/notifications` returns 201 carrying a
        `Notification` with `sent_at`. Failure paths: a blank or absent `reason`
        → 400 with no notifier call, an unknown item → 404, a notifier that
        raises → 502.
  - [ ] `POST /api/projects/{project_id}/tracker-items/{item_id}/actions`
        returns **404**: the route is gone, and `generate_document` and
        `stakeholder_link` answer by absence rather than by a documented 500
        (D76). One test asserts the 404.
  - [ ] `web/src/api/client.ts` drops `TrackerAction` and `postTrackerAction`
        and gains `postEmailDraft(projectId, itemId)` and
        `postNotification(projectId, itemId, reason)`; `TrackerDashboard.tsx`
        calls them, and `runMutation` becomes generic so a `Notification`
        result leaves the row untouched instead of replacing it. The web
        typecheck and tests pass.
  - [ ] The three operations join `tracker.py`'s `PATHS`; the drift test passes
        and the removed `/actions` entry is gone from the document too.
  - [ ] Gate: `./.claude/init.sh check`.
- Files: `src/clearcut/application/get_tracker_item.py`,
  `src/clearcut/adapters/http/tracker.py`, `src/clearcut/composition.py`,
  `tests/unit/application/test_get_tracker_item.py`,
  `tests/unit/adapters/test_tracker_routes.py`,
  `tests/unit/test_composition.py`, `web/src/api/client.ts`,
  `web/src/api/client.test.ts`,
  `web/src/components/organisms/TrackerDashboard.tsx`
- Notes: `ResolveFinding` keeps its shape — `Notify` still returns the item
  unchanged and the route builds the 201 `Notification` body, so no use case
  learns about HTTP. No live test (D83); the notifier's live coverage stays
  CP-059's, which is still blocked on `NOTIFY_WEBHOOK_URL`.

### CP-074 — Serve the project bible and let a producer add facts
- Status: TODO
- Attempts: 0/3
- Depth: 0
- Layer: application
- Depends on: CP-070
- Acceptance:
  - [ ] `GetBible(lore).execute(project_id)` returns a `ProjectBible`;
        `AddBibleFacts(lore).execute(project_id, drafts)` numbers new facts from
        `next_fact_number(lore.facts(project_id))` and indexes them, returning
        the created `BibleFact`s.
  - [ ] Unit tests: adding two facts to a bible holding `FACT-001` returns
        `FACT-002` and `FACT-003`, and both reach `lore.index` exactly once.
        Failure paths: an unknown `kind` raises rather than indexing, an empty
        `facts` list is refused, and a `LoreStore` outage propagates as
        `SourceUnavailable`.
  - [ ] `GET /api/projects/{project_id}/bible` returns 200 and
        `{project_id, facts: [...]}`; in mock mode the array contains
        `FACT-001`.
  - [ ] `POST /api/projects/{project_id}/bible/facts` returns 201 and an array
        of the created facts. Failure paths: an invalid `kind` → 400, a missing
        `text` → 400, an empty `facts` array → 400, and no `index` call in any
        of them.
  - [ ] `adapters/http/bible.py` is added to `DOMAINS` in `openapi.py` and
        registered in `composition.py`; the drift test passes, both operations
        are tagged `Bible`, and the document now carries all six tags.
  - [ ] Gate: `./.claude/init.sh check`.
- Files: `src/clearcut/application/{get_bible.py,add_bible_facts.py}`,
  `src/clearcut/adapters/http/{bible.py,openapi.py}`,
  `src/clearcut/composition.py`,
  `tests/unit/application/{test_get_bible.py,test_add_bible_facts.py}`,
  `tests/unit/adapters/test_bible_routes.py`,
  `tests/unit/test_composition.py`
- Notes: This closes the endpoint ADR 0011 cut and CP-057's block called "a real
  product gap: a producer cannot upload a bible in the demo". `next_fact_number`
  comes from CP-061 and `LoreStore.facts` from CP-066, so this touches neither
  the domain nor an adapter. No live test (D83).

### CP-075 — Finish the API client against the partitioned API
- Status: TODO
- Attempts: 0/3
- Depth: 0
- Layer: adapters
- Depends on: CP-071, CP-072, CP-073, CP-074
- Acceptance:
  - [ ] `web/src/api/client.ts` gains the types `Project`, `ProjectSummary`,
        `TrackerCounts`, `CreateProjectRequest`, `Jurisdiction`, `ScriptFile`,
        `ScriptSummary`, `Notification`, `Bible`, `BibleFactDraft` and the
        functions `listProjects`, `createProject`, `getProject`,
        `listJurisdictions`, `uploadScriptFile`, `listScripts`, `getScript`,
        `getTrackerItem`, `getBible`, `addBibleFacts`.
  - [ ] `uploadScriptFile(projectId, file)` sends `FormData` and sets **no**
        `Content-Type` header, so the browser writes the multipart boundary. One
        test asserts the header is absent — setting it is the failure that makes
        every upload 400 and is invisible to a type check.
  - [ ] Each function has a test asserting the exact path it calls and the
        shape it returns; `client.ts` remains the only file containing `/api/`
        literals, which the `web/` tests already enforce.
  - [ ] Failure path: a non-2xx response raises with the server's error message
        rather than resolving to `undefined`, for every new function.
  - [ ] The fixtures under `web/src/fixtures/` keep their existing shapes and
        `fixtures.test.ts` passes, so the SPA's rendering tests are unaffected.
  - [ ] Gate: `./.claude/init.sh check`, which runs the `web/` typecheck, tests
        and stylelint.
- Files: `web/src/api/client.ts`, `web/src/api/client.test.ts`,
  `web/src/fixtures/` if a shape moved
- Notes: No component gains a new screen here — the santree-style SPA rebuild is
  a separate plan and does not touch this board. This checkpoint makes the
  client able to call every resource; wiring screens onto it is later work.

### CP-076 — Write down the API the partition produced
- Status: TODO
- Attempts: 0/3
- Depth: 0
- Layer: docs
- Depends on: CP-071, CP-072, CP-073, CP-074
- Acceptance:
  - [ ] `docs/plan/adr/product/0012-api-partitioned-by-domain.md` exists and, as
        prose a reviewer judges against `.claude/WRITING.md`, states: that it
        amends ADR 0011 rather than replacing it, and why the three cut
        endpoints came back (D75); the `/actions` split and why an unbuilt
        feature 404s instead of 500ing (D76); the tracker key defect, its
        symptom, and the migration it forced (D77); the constructor and
        composition size arguments (D78, D79); and the four deliberate limits
        with the reason each was accepted (D80). A reader who was not in the
        room can tell what was decided and what it cost.
  - [ ] `docs/plan/sdd.md` §3's port table and §4's route table match the
        shipped code: no route is listed MISSING that now exists, none is listed
        that no longer exists, and each carries its status codes. A reader
        comparing §4 to `/api/openapi.json` finds the same set of paths.
  - [ ] `README.md:26-30` no longer documents `POST /api/analyze`; its curl
        sequence is one a reader can paste in order against mock mode, verified
        by running it rather than by reading it.
  - [ ] `docs/plan/infrastructure.md` §6 lists four ClickHouse tables with their
        engines and sort keys, and §8 carries `SCRIPTS_INTAKE_BUCKET`.
        `tests/unit/test_environment_contract.py` is bidirectional, so §8 and
        the required set cannot disagree.
  - [ ] No document claims a checkpoint is `DONE` that a reviewer has not
        passed, and none claims the deployed revision serves the new API before
        CP-077 has deployed it.
  - [ ] Gate: `./.claude/init.sh check`.
- Files: `docs/plan/adr/product/0012-api-partitioned-by-domain.md`,
  `docs/plan/sdd.md`, `README.md`, `docs/plan/infrastructure.md`
- Notes: The deliverable is prose, so `.claude/WRITING.md` findings are blocking
  for this checkpoint rather than deferred. Parallel with CP-075: disjoint
  files.

### CP-077 — Migrate and redeploy, after the human confirms the data loss
- Status: TODO
- Attempts: 0/3
- Depth: 0
- Layer: infra
- Depends on: CP-067, CP-075, CP-076
- Acceptance:
  - [ ] **Stop and ask first.** `provision_tracker_schema.py --recreate` drops
        the deployed demo tables and the tracker history goes with them. The
        implementer asks the human explicitly and records the answer in this
        block before running anything. Without that answer the checkpoint goes
        `BLOCKED`, not ahead.
  - [ ] `provision_tracker_schema.py --recreate` has run against the real
        ClickHouse service, and all four tables exist with their new sort keys —
        verified by querying `system.tables`, not by reading script output.
  - [ ] The demo project's legacy lore rows, which carry no `fact_id`, are
        deleted from BigQuery before reseeding; `seed_project_bible.py` then
        writes the project row and the 8(d) fact, and
        `GET /api/projects/demo-project/bible` returns exactly one `FACT-001`
        rather than a duplicate.
  - [ ] The planted script v1 is re-POSTed through
        `POST /api/projects/demo-project/scripts` and returns 201, and
        `GET .../scripts` then lists it.
  - [ ] `./.claude/init.sh live` is green with credentials present, including
        every live test CP-063, CP-064, CP-065, CP-066 and CP-070 added.
  - [ ] `gcloud run deploy --source .` puts a new revision behind
        `https://clearcut-813918777633.us-central1.run.app`, and against **that
        URL**: `/api/docs` shows six collapsible groups (Projects, Scripts,
        Tracker, Bible, Questions, System); "Try it out" on
        `GET /api/jurisdictions` returns ten rows; `/api/openapi.json` has six
        tags and as many unique `operationId`s as operations;
        `POST .../tracker-items/EVT-001/actions` returns 404; and
        `GET /api/health` reports `live`, not `mock`.
  - [ ] Failure path, recorded rather than worked around: if the deployed
        revision serves `mock`, or a live test fails against the migrated
        tables, this checkpoint reports it and stops. A green local run is not
        evidence about a deployed revision — that confusion is what §5 exists to
        prevent.
- Files: none in `src/`. Evidence goes in this block; `infra/README.md` and
  `docs/plan/infrastructure.md` only if a documented step proves wrong in
  practice, which CP-055 shows is the likely outcome.
- Notes: This is the live proof for every HTTP checkpoint above (D83): the curl
  and Swagger checks are real requests to the real service, which no test client
  can substitute for. It does not close CP-060 — that checkpoint is judged on
  its own criteria by its own reviewer (D74).

---

**How this board closed twice before, and why that history still binds.**

The approved Browser MVP plan was delivered. CP-052, CP-053 and CP-054 all passed
review and are archived, committed as `2172574`, `f3f025e` and `1362bc1` with
their loop-state chores. **Fifty-four
checkpoints, fifty-two `DONE` and two `SUPERSEDED`** (CP-028 and CP-030, each
split once into `Depth: 1` replacements that landed), CP-001 through CP-054 with
no gaps, every one behind a review that ran the gates.

What that bought, against the two gaps the plan named. **It runs:** an entrypoint
exists, `./.claude/init.sh` installs the project, `.env` loads, `CLEARCUT_MODE`
is documented, and the README carries a two-command story whose curl order was
verified rather than assumed. **It shows:** the three surfaces render in a
browser over an API client that now matches the server field for field, and
`init.sh check` runs the frontend gates that had never run — which is why the
contract drift CP-053 repaired had survived every previous review.

**One commit sits outside this loop, and it is the only one.** On 2026-09-02 the
user rejected the shipped UI and ordered a design pass; it ran as delegated-direct
work with an adversarial review and landed as `349da37`, 13 files under `web/`.
It is not a checkpoint and has no block in the Archive, so `git log` and that
Archive no longer tell quite the same story — which is why D63 records it. The
board stayed terminal throughout: a direct user order is not an agent reopening
its own board, and section 6's two rules bind agents, not the person the loop
reports to.

Two rules governed the emptiness both times, and they govern this reopening too.
A leader adds checkpoints only for a new human goal or a `BLOCKED` checkpoint,
never in response to a `PASS`; and `BLOCKED` never returns to `TODO`. Between
them no agent can walk this board from "finished" back to "in progress" on its
own. The board has now reopened exactly twice, on 2026-09-01 (D53) and on
2026-09-03 (D67), and both times it took a human approving a plan to do it —
which is the mechanism working, not an exception to it.

**The Backlog below is not a queue this loop drains.** Every entry carries its
date, its reasoning and the trigger that would justify promoting it. As of
2026-09-02 no trigger fires before 2026-09-07, and the four entries most likely
to matter afterwards are grouped at the top of the newest block in rough severity
order rather than in the order their reviews happened to find them.

**Where the record is.** Each checkpoint's evidence sits with its block in the
Archive, newest first: the criteria as written, what the implementer built, and
what the reviewer re-ran rather than took on trust. Each decision that shaped the
plan is in `## Decisions`, D1 through D62, with the reasoning that produced it,
because the next person to read this file is the one who will want to reopen one
of them and a decision without its reasoning gets re-litigated.

---

## Backlog

Not checkpoints yet. Phase 4 and the first half of phase 5 were promoted into
CP-018 through CP-030 on 2026-08-30; what is left here is what was ruled out of
this batch, each with the date and the reason, so nothing was dropped silently.

Everything below was weighed against the same tiebreak: does it protect the
2026-09-07 demo? An item that does not can wait, and the reason it waits is
written down so the next turn re-decides on evidence rather than re-litigating.

**Carried from CP-001's review, independent of every phase.**

- Format `.claude/lib/termination.py` and drop `extend-exclude = [".claude"]`
  from `pyproject.toml:21`. The exclude was correct for CP-001's scope, but it
  keeps the loop's only Python module outside both ruff gates.
- ~~Make `tests/integration/` survive a commit.~~ Absorbed by CP-012 (D4),
  which puts an `__init__.py` in every directory under `tests/`.
- ~~Pin `_package_for` in `tests/unit/test_layer_boundaries.py`.~~ **Absorbed by
  CP-050 (D39)**, which narrows the adapters exclusion to same-package siblings
  and therefore computes its allowance through this function — promoting the pin
  from a coverage gap to a prerequisite. The original entry, kept for its
  evidence: a test asserting that both a regular module and an `__init__.py` map
  to `clearcut.domain`. Mutant C (returning `".".join(parts)`) survived all seven
  tests during review because the three relative-import tests pass the package
  string literally and never route through `_package_for`. Under that mutant,
  `from ..adapters import x` in `domain/jurisdiction.py` resolves to
  `clearcut.domain.adapters`, satisfies the `startswith("clearcut.domain.")`
  allowance, and is waved through — escape detection silently off for real
  files while the suite stays green. Today's behaviour is correct; this is a
  coverage gap, not a defect.

**Phase 4 and 5, promoted 2026-08-30.** `TrackerItem` and its two ports,
dedupe, `diff_scenes`, the confidence rule, the contradiction check, the
ClickHouse and webhook adapters, all four use cases, the Flask routes, and
`composition.py` are now CP-018 through CP-030. What follows is what stayed
behind.

**Deferred out of the phase-4 batch, 2026-08-30, each with its reason.**

- ~~**OpenTelemetry (SDD §6), and the Grafana dashboard §8(d) checks.** D14.~~
  **Promoted to CP-031 on 2026-08-30**, when the user overturned D14: SDD §6 and
  ADR 0008 both specify observability as a launch requirement, on a standing
  instruction from the user that the triage had not weighed. See the D14
  amendment. What stays in the Backlog is the part that needs live
  credentials — building the Grafana dashboard and confirming a demo run's
  traces reach it — which belongs with the SDD §8 live checks below.
- **Multipart PDF upload, with the `ScriptStorage` port it needs.** D10.
  CP-029 takes a `gcs_uri` instead; the operator runs `gcloud storage cp`. This
  is the SPA's dependency, not the demo's, and it removes a port, an adapter,
  and a checkpoint from the critical path.
- **`GET /api/scripts/{script_id}`.** Re-reads findings that nothing persists —
  there is no findings table in `infrastructure.md` §6 and no port for one. SDD
  §4.1 step 8 has the analyze response carry scenes, findings, and items, so
  the SPA's first view works without it. Needs a storage decision before a
  checkpoint, not during one.
  **Two more consequences of the same missing table, added 2026-08-31 by
  D37.** Read them here rather than as separate entries; one table answers all
  three.
  *(i) A delta run's `report.findings` covers only the ADDED and CHANGED
  scenes.* An UNCHANGED scene is never re-extracted, by design, and nothing
  persisted its v1 findings, so `EvaluateDelta` has nothing to put in the
  response for it. CP-041 maps that report onto `POST /api/analyze`, so a v2
  upload renders a findings overlay covering the changed scenes beside a
  tracker table covering the whole project. Not fixable cheaply: labelling the
  payload as partial adds a key that D30 and CP-041's second criterion forbid,
  because `web/src/api/client.ts` renders both paths from one shape. What holds
  in the meantime is that `tracker_items` in that same response covers every
  item, so the clearance record a producer acts on stays complete.
  *(ii) Carry-forward cannot match on asset identity.* `TrackerItem` carries no
  `category` and no `raw_text`, `TrackerStore` exposes no findings read, and
  this table is why. See the entry below.
- **Persist asset identity on a tracker item, so a clearance survives a scene
  move.** Added 2026-08-31 by D37, after CP-028's review measured the gap and
  the checkpoint was superseded rather than widened. The work: `category` and a
  normalized `raw_text` on `TrackerItem`, two ClickHouse columns and the
  migration behind them, a `latest_for_project` read that returns them, and a
  match in `EvaluateDelta` on the pair instead of on scene overlap. It reopens
  two `DONE` archives (CP-023's adapter, CP-025 and CP-036's domain module) and
  costs four implementer turns and four reviewer turns on the critical path,
  seven days before 2026-09-07, for a case the demo does not run — SDD §7 phase
  5 uploads v2 with one edited scene, which keeps its number and joins as
  CHANGED. **The consequence while it waits, stated plainly because D37's
  ruling depends on it being visible:** an asset edited out of one scene and
  added in another arrives as a new item at BLOCKED and a human clears it a
  second time, while the item it left behind stays open, flagged for re-review,
  and carrying a note naming the scene it was cleared against (CP-044). Nothing
  is dropped and nothing is kept without saying so; what is spent is a repeated
  clearance. ADR 0007 and SDD §4.3 say this outright once CP-045 lands.
- **`POST /api/projects` and `POST /api/projects/{id}/bible`.** Same root cause:
  a project record and a bible store that no port and no table cover. The demo
  seeds bible facts straight into the LoreStore, which is what SDD §8(d)'s
  "a seeded bible fact" already assumes.
- **`generate_document` and `stakeholder_link` tracker actions (SDD §4.2).**
  CP-025 covers the other two. `generate_document` is another model call and
  therefore another port; `stakeholder_link` returns a registry link
  `RightsResearch` has not been asked to resolve. Both are half-features until
  those two questions are answered.
- **LoreStore deletion for CHANGED scenes (SDD §4.3).** CP-028 left it out and
  CP-044 leaves it out too: it needs a `delete` method the frozen `LoreStore`
  port lacks, and adding one reopens a `DONE` adapter. Known limitation while
  it waits — a changed scene leaves a stale row that later retrieval can return
  as history. Harmless for a two-version demo, wrong for a series.
  **Amended 2026-08-31 by D37:** SDD §4.3's second bullet currently promises
  the deletion in a parenthetical, so the specification describes code that
  does not exist. CP-045 replaces that parenthetical with a sentence saying it
  is unbuilt and why. The limitation stays here; only the claim goes.
- **`Scene.number` is an `int`, so a production A-scene (`14A`) cannot be
  represented.** Found while ruling D19, and recorded because it is the
  counterweight to that ruling rather than support for it: inserting `14A` is
  how a locked script avoids renumbering everything below it, and ClearCut
  cannot express it, so a real v2 insert renumbers and pays the full
  re-analysis D19 accepts. Changing the type reaches `Scene`, `SceneDelta`,
  `Finding.scene_number`, `TrackerItem.scene_numbers`, the ClickHouse schema,
  and the SPA — a domain-wide change with no demo beat behind it, eight days
  out. It is the honest fix for the cost D19 accepts; the join key is not.
- **The one-line scene summary flash-lite writes as LoreStore row metadata**
  (SDD §4.1 step 5). D11 kept it out of `ContinuityCheck`. Nothing reads it.
- **A jurisdiction set on `TrackerItem`, and the territory filter it would
  enable.** D26, from CP-027's reviewer. `agentic-workflow.md` §6 describes
  "What is still blocking release in Mexico?" as a query for BLOCKED items
  whose jurisdiction set includes Mexico; the field does not exist, so the
  answer lists every blocked item. Declined because a per-item jurisdiction
  *set* only means something once one project is analyzed against several
  jurisdictions, and nothing builds that — `extract`, `ground`, `AnalyzeScript`
  and `POST /api/analyze` each take exactly one. Every item a run produces
  therefore shares that run's jurisdiction, so today's unfiltered answer is
  correct rather than merely harmless. Unlike D24's gap this one gets *cheaper*
  to fix later, because its shape depends on the multi-jurisdiction analysis it
  waits behind. CP-037 makes the current answer honest in the meantime by
  naming the territory it covers.
- **The keyword-call-site guard on the five concrete adapters.** D15. Struck
  for now; the rule "use cases call port methods positionally" closes the gap
  at the only call sites that exist. Revisit when the number of call sites
  makes a convention unreliable.
- **A raise-site guard for stdlib exceptions crossing a port.** D27, from
  CP-034's review. CP-034's contract walk collects module-owned `Exception`
  subclasses, so `raise ValueError` inside a port method is invisible to it and
  no widening of that walk would see it — catching that shape needs a third
  structural guard doing an AST scan of `raise` statements under `adapters/`.
  Deferred because the rule has exactly three known sites and D27 ruled all
  three: two are unreachable from a validated request and one fires at startup,
  where CP-030 already owns it. What holds the line in the meantime is
  behavioural, not structural — CP-029 returns a JSON 500 for any unmapped
  exception, `ValueError` included, asserted by a test. Worth building the day
  a fourth site appears, or the day one of the three becomes reachable again.
- **Cloud Run deploy script under `infra/`**, completing D6's scope: the §9
  deploy with `--set-secrets`, `--set-env-vars`, `--runtime python312` (D8),
  the service account roles, and `min-instances 0`. Same `--dry-run` seam and
  test shape as CP-013. It unblocks once CP-030 lands `create_app()`.
  **It also carries D17**: `infra/README.md`'s run order jumps to
  `gcloud storage ls "gs://clearcut-legal-corpus/**"` without ever telling a
  human to upload the legal PDFs into that bucket first. Same file, same
  numbered list, two lines — attached here so it cannot be lost.
- **The three SPA surfaces against the live API, replacing CP-011's fixtures.**
  The first of them carries D18's two items: wrap `requestJson`'s
  `response.json()` so malformed JSON inside a 200 surfaces as `ApiError`
  rather than a raw `SyntaxError` (`web/src/api/client.ts:108`), and add
  Tailwind — config plus the first class that a test actually exercises, which
  is what CP-011 correctly declined to add with nothing exercising it.
  **D36 changed what this waits on, 2026-08-31.** It waited on live services;
  mock mode gives it a running API with no credentials, so the only thing in
  front of it is CP-030. It is therefore the first promotion candidate for the
  next leader turn, and the argument for promoting it is blunt: a mocked MVP
  the user can only see through `curl` is not the MVP the decision asked for.
  Not promoted this turn, because it is three surfaces and two carried items,
  and nothing in it can start before CP-030 lands anyway.
- **SDD §8(d) end-to-end check on the planted script.** The Ferrari Testarossa,
  "Hotel California", and one seeded-bible contradiction. Runs after CP-030,
  against live services, and it is the submission's evidence.
  **Amended 2026-08-31 by D36.** The same three assertions now also run mocked,
  as a criterion on CP-030, so this entry is the *live* run only. It stays the
  submission's evidence and does not become redundant: the mocked run proves
  the wiring, this one proves the services.
  **Amended 2026-09-03 by D66.** This entry named the defect a year of green
  gates could not see, and then sat here with no `*Trigger:*` — which is how it
  stayed unpromoted through two terminal boards. The tier it was waiting for now
  exists (`tests/live/`, `./.claude/init.sh live`), so what remains here is the
  §8(d) run itself. *Trigger:* the `clearcut-hack` project existing and
  `./.claude/init.sh live` passing with credentials present.
  **Promoted to CP-059 on 2026-09-03 by D67**, without waiting for that trigger:
  ADR 0011 makes provisioning CP-055 rather than a precondition, so the trigger
  is now a dependency edge instead of a reason to wait.

**Carried from the five adapter reviews, ruled non-demo-critical 2026-08-30.**

- `Citation.snippet` mapping is untested (`research.py:143`,
  `snippet=(c.excerpts or [""])[0]`); mutating it to `""` leaves all six CP-010
  tests green. A coverage gap on a display field.
- Four mypy-forced defensive branches in `research.py` carry no test
  (lines 113-115, 120-121, 143, 148-149). Individually minor, grouped here as
  CP-010's reviewer grouped them.
- `web/`: `ScriptViewResponse` omits `gcs_uri`, which SDD §2 lists on `Script`.
  Leaving an internal storage URI out of a browser payload is defensible;
  the route that emits the payload decides, not the client.
- `web/`: `tsconfig.json` sets `include: ["src"]`, so `vite.config.ts` is never
  type-checked. Harmless now, worth folding in when that config grows.

**Placed 2026-08-31: reviewer findings that were recorded but never ruled.**

An audit this turn found seven non-blocking items sitting in archived review
notes and in the Decisions preamble, in neither a checkpoint nor this section.
One became CP-047 above. The other six are recorded here with their reason, so
the loop's own rule holds for them too: a non-blocking finding becomes a
checkpoint or a dated declination, never a silence. None is on the SDD §8(d)
path and none blocks CP-030, CP-031 or CP-041.

- **A timestamp the caller controls, on the two tracker routes.** CP-029's
  review, item 1. `at = _now()` is minted server-side, but a mutant that reads
  `at` from the request body survives on `PATCH /api/tracker/{item_id}` and
  `POST /api/tracker/{item_id}/actions`. The code is right; the guard is
  missing. `updated_at` on a tracker row is clearance audit data, and CP-029's
  own criterion phrased the rule for `/api/analyze` only, so this is a coverage
  gap rather than an unmet criterion. Worth one checkpoint covering both sites.
- **`_json_body`'s non-dict guard is untested.** CP-029's review, item 2. A
  valid-JSON-but-not-an-object body maps to `{}`, and removing the guard leaves
  the suite green. It is load-bearing: `_json_body` runs outside
  `_run_use_case`'s try, so without it the `AttributeError` escapes the mapping
  entirely and the demo shows a Flask traceback — the exact failure CP-029's
  500 criterion exists to prevent.
- **`web/src/api/client.ts` types `contact` as an object.** CP-029's review,
  item 3, the half CP-047 does not take. `TrackerContact | null` against
  `contact: str` in `domain/tracker.py`, which the route serializes faithfully.
  A frontend change, and it belongs with the three SPA surfaces above, which
  rewrite that file anyway.
- **`_require_field`'s docstring claims a strip it does not perform.** CP-029's
  review, item 4. It returns the raw value and uses `.strip()` only for the
  blank check, so a padded `project_id` reaches the LoreStore with its
  whitespace. No criterion names trimming, so this is a docstring correction or
  a one-line behaviour change, whichever a later turn prefers — not a defect
  against a stated contract.
- **The demo cites trademark law for an Eagles song.** CP-043's review, item 2.
  One shared `GROUNDED_ANSWER` was upheld as correct, but its only citation is
  Ley de Marcas 22.362, so the `MUSIC_EXISTING` finding renders grounded in
  trademark law on the SDD §8(d) screen. The fix is data — a second `Citation`
  on the same tuple — with no rule and no format duplicated. The strongest
  promotion candidate of the six, because it is what a judge reads.
- **`InMemoryRightsResearch.find` raises a bare `KeyError`.** CP-043's review,
  item 3. The live adapter raises the domain error and `AnalyzeScript` degrades
  that one finding; the demo adapter raises a stdlib error nothing catches, so
  mock mode returns 500 where live mode degrades. Unreachable while
  `InMemorySceneExtractor` emits only the two seeded assets, and reachable the
  moment mock mode serves a third. It is also the one place left in the tree
  that contradicts D23's convention.

*Corrected rather than filed as work.* CP-043's review also flagged that a
Notes sentence in that block overreaches on project scoping. The accurate
statement, recorded here because a `DONE` block is not reopened for its prose:
the demo stores are project-scoped on `latest_script` and `search` only; the
five unconditional read-only ports, continuity included, are not. That is what
a mock is, and no criterion required otherwise.

**Placed 2026-09-01: the deferred queue CP-031, CP-046, CP-049 and CP-050 left
behind (D41–D47).**

Ten findings sat unruled in archived Notes from the last two days of reviews. One
became CP-051 (D40), one was declined outright with its reasoning (D45, latency
on the failure path), two were editorial fixes to this file (D48, D49). The six
below are deferred, each with the date, the reason, and — because an empty board
invites promotion for its own sake — **the trigger that would make it worth
promoting**. None is on the SDD section 8(d) path and none affects the mocked
demo, which is the run the judges watch (D36).

- **Three live env values no test can prove reach their adapter.** D41, from
  CP-049's attempt-2 review. A hardcoded `PARALLEL_API_KEY`
  (`research.py:95-100` keeps the constructed `Parallel` client, never the key)
  and a hardcoded `GOOGLE_CLOUD_PROJECT` in either `genai.Client`
  (`composition.py:231`) or `VertexAIEmbeddings` (`composition.py:221`) all
  survive the full suite. Closing them needs a vendor-internal attribute read
  (`client.api_key`, `VertexAIEmbeddings`'s pydantic `project` field — coupled to
  the version, though both pins are exact `==`) or an adapter change that stores
  the value. Deferred because of what the mutants model: every mutant CP-049 did
  close modelled silence, while these fail loudly at the first live call — or, in
  the most likely instance, a developer hardcoding `clearcut-hack`, behave
  correctly by accident. The three `CLICKHOUSE_*` values are not in this class;
  criterion 6's test already kills a hardcoded substitution for them.
  *Trigger:* a second Google Cloud project, or an adapter that needs the key for
  anything besides constructing its client.
- **`answer_project_question`'s tracker is asserted by type, not identity.** D42,
  from CP-049's attempt-2 review. Wiring it to a second
  `ClickHouseTrackerStore(ch_client)` rather than the shared instance leaves the
  suite green; `test_build_live_use_cases_shares_the_seamed_clients_across_use_cases`
  covers three use cases and not the fifth. Deferred because that store holds the
  client and no other state, so the surviving mutant is a runtime no-op; the
  mutant that would matter, a store over a second real client, opens a socket and
  dies on `_forbid_sockets`. One line when someone next opens that test.
  *Trigger:* any per-instance state landing on `ClickHouseTrackerStore`.
- **`VertexAIEmbeddings` emits a `LangChainDeprecationWarning` on every live
  build.** D43, from CP-049's attempt-1 review. Deprecated in LangChain 3.2.0,
  removed in 4.0.0, and `langchain-google-vertexai` is pinned `==3.2.4` — so the
  removal cannot reach this repo until a human edits that pin, and nothing before
  2026-09-07 does. Costs one warning line per live `create_app()`, on a path the
  demo does not run. Recorded so whoever performs the bump reads this first
  instead of meeting it as an `ImportError`. *Trigger:* the pin moving.
- **Six near-identical `_record_stage` helpers, and `test_observability.py`'s
  copies of the `conftest.py` ones.** D44, from both CP-031 reviews.
  `_record_stage` in `gcp/document_ai.py`, `gcp/vertex_search.py`,
  `parallel/research.py`, `clickhouse/tracker.py` and `demo/in_memory.py`, a
  sixth variant `_record_stage_latency` in `gemini/extractor.py`,
  `_refresh_tracker_items_gauge` in two, plus `test_observability.py:61` and
  `:251` as byte-for-byte duplicates of `install_in_memory_telemetry` and
  `metric_attributes_by_name`. Deferred because this is under-abstraction, which
  Section 4 does not ban, and because consolidating it touches five live adapters
  and the demo module — all `DONE`, all mutation-verified — for zero observable
  behaviour change. "Duplicate twice, extract on the third" guides code being
  written; it is not a warrant to rewrite code that is finished, six days out.
  *Trigger:* a seventh span site.
- **CP-046's criterion-4 import-time property is unpinned.** D46, from CP-046's
  attempt-1 review. Hoisting `_default_build_dir()`'s body to a module-level
  constant leaves the suite green, because
  `test_create_app_serves_whichever_build_dir_is_passed_in` passes both
  directories explicitly and cannot see the difference. The parameter itself is
  pinned; only "computed at import time" is not. Deferred because the surviving
  mutant costs almost nothing — the default would be computed once per process
  instead of once per call, and the repo root does not move during a process. The
  instructive comparison is the `_package_for` pin, the same class of gap, which
  D39 *did* promote because CP-050 made it load-bearing for a gate's correctness;
  nothing makes this one load-bearing. The test shape, recorded so it is not
  re-derived: assert that importing `clearcut.composition` touches no filesystem.
  *Trigger:* anything in `composition.py` growing a second import-time
  computation.
- **The layer gate's same-package allowance covers the package name and no
  deeper form.** D47, carrying all three of CP-050's non-blocking notes. Exact
  equality is what criterion 3 asked for, so inside `adapters/demo/in_memory.py`
  the ordinary `from .scenario import DEMO` and
  `from clearcut.adapters.demo.scenario import DEMO` both come back as
  violations they did not earn; a parent-package import is likewise rejected from
  inside a module's own subpackage, where the criteria are silent. Deferred
  because the gate errs strict, and strict is the right side to be wrong on: a
  red gate on a legitimate import stops a person for a minute and says what it
  thinks is wrong, while a carelessly widened one permits the cross-package
  import that is D36's silent failure and CP-050's whole reason to exist. The
  trigger cannot fire before the deadline either — nothing left on the board
  writes an adapter. Folded into the same entry, for one turn in that file:
  `tests/unit/test_layer_boundaries.py:6-9`'s module docstring still attaches the
  carve-out to the `adapters/` package, which is the wholesale skip CP-050
  removed. *Trigger:* the next adapter written, or any sibling import in that
  package that is not the package form.

**Placed 2026-09-01: the three findings CP-051's PASS deferred (D50–D52).**

CP-051 passed with zero blocking findings and reported three non-blocking ones.
AGENT.md section 6 forbids a checkpoint in response to a `PASS`, so all three are
ruled here rather than promoted. None is declined — each changes what a
maintainer or a deployer meets. This is the last entry the loop adds; everything
below this line is now a human's to pick up or leave.

- **`infra/README.md:40` tells a deployer to copy a variable that no longer
  exists.** D50, from CP-051's review. Step 7 still says to copy
  `AGENT_BUILDER_AGENT_ID` from the script's output into `.env`; CP-051 struck
  that variable from all three surfaces it owned, so the instruction names a
  value the output no longer prints and nothing reads. Deferred because it fails
  safe, which is what separates it from the gap CP-051 closed: the service still
  starts — nothing requires the variable, which is why it was struck — so the
  cost is a confused deployer, not a broken deployment. **Fix it in the same turn
  as D17**, which is already open against this exact file and this exact numbered
  list: the run order jumps to `gcloud storage ls "gs://clearcut-legal-corpus/**"`
  without telling a human to upload the legal PDFs into that bucket first. Two
  stale steps in one procedure. *Trigger:* anyone opening `infra/README.md`, or
  the Cloud Run deploy entry above being promoted, whichever comes first.
- **The environment guard's AST filter skips five call shapes in silence.** D51,
  from CP-051's review. `tests/unit/test_environment_contract.py:44-53` matches
  only a string-literal first argument to a bare `_required_env` name; a variable
  argument, an f-string, a `name=` keyword, a loop over a tuple, and a
  module-qualified call are each skipped without a word. The failure direction is
  the bad one — a guard that quietly stops covering a call site lets back exactly
  the drift CP-051 was filed to end. Deferred because the hole is entirely in the
  future: all ten call sites in `composition.py:196-205` are bare calls passing a
  string literal, verified this turn, so coverage is complete as the tree stands.
  **The fix is the reviewer's, and it is not a wider parser:** assert that every
  `_required_env` call site passes a string literal, so an unhandled shape
  announces itself instead of being skipped. *Trigger:* the first `_required_env`
  call written in any other shape, or any refactor of that block.
- **Section 9's deploy command is guarded by nothing, and the reverse direction
  keys on `_required_env` rather than on reads under `src/`.** D52, from CP-051's
  review, both halves in one entry because one turn in that file should settle
  both. The guard covers `.env.example` and the section 8 table; section 9 is a
  third surface, correct today and held there by nothing — and it is the surface
  D40 found last and by inspection, so it has drifted once already. What limits
  the risk is that it shares a document with the table the guard does cover, so a
  maintainer adding a variable gets a loud failure three sections away from the
  command. The second half is a trap with a misleading message: documenting
  `CLEARCUT_MODE`, which `composition.py:78` genuinely reads, fails with a message
  saying nothing requires it. `OPTIONAL_ENV_VARS` is the one-line fix.
  *Trigger:* any variable added to the section 9 command, or the first optional
  variable someone tries to document.

**Placed 2026-09-02: the deferral queue the localhost plan's six reviews left
behind (D54–D62).**

Ten non-blocking findings from CP-052, CP-053 and CP-054. Nine are deferred here
in eight entries — two of them must be fixed in one turn and say so — and one is
declined outright (D59, the `/api/` spellings in three `it()` titles: the
architecture gate permits them by design, the titles are accurate, and a drifted
test title misleads nobody about behaviour pinned elsewhere). Ordered by what
they cost rather than by which review found them. Five days remained to
2026-09-07 when these were ruled, and no trigger below fires inside it.

- **`load_dotenv()`'s no-override contract is proved by nothing.** D54, from
  CP-052's review. `main.py:14` — removing the import and the call outright
  leaves the whole unit suite green, and `load_dotenv(override=True)` is equally
  invisible while no `.env` exists. **The highest-severity entry on this list:**
  the no-override default is what makes `CLEARCUT_MODE=live ./.venv/bin/python
  main.py` beat a copied `.env` carrying `CLEARCUT_MODE=mock`, so flipping it
  serves planted demo data to an operator who believes they are on live services
  — D36's named failure. Deferred only because nothing before the deadline opens
  that file. *Trigger:* the first edit to `main.py`, or the day a `.env` ships
  inside a deployment image. Close it before doing anything else in that file.
- **`PORT` is undocumented, and the test covering it depends on `.env` being
  absent.** D55, from CP-052's review, **one entry because fixing either half
  alone makes things worse.** `main.py:22` introduces `PORT`, which no document
  records and CP-051's guard cannot see (it parses `_required_env` in
  `composition.py` only). `tests/unit/test_entrypoint.py:93`'s
  `test_port_defaults_to_8080` reddens against an unmodified `main.py` if a root
  `.env` carries `PORT=7777`, because `load_dotenv()` injects it before `_port()`
  reads it. Documenting `PORT` is an instruction to put it in a real `.env` —
  which is exactly the condition that reddens the test — so **the test's
  env-independence lands first, or in the same turn, never after.** *Trigger:*
  anyone documenting `PORT`, or a developer hitting the red test.
- **The web fixtures have drifted from the wire scenario.** D60, from CP-054's
  review. `tracker.json` and `analyze.json` carry `item_001`/`fnd_001`-style ids
  where the server serves `EVT-001`..`EVT-003`, documents "Product placement
  release" / "Synchronization license" / "Location permit" where the wire serves
  "Trademark Clearance Form" / "Synchronization License" / "Continuity
  Revision", and notes on two rows where the live continuity item carries `""`.
  Deferred because it **cannot reach the demo** — verified this turn, the
  fixtures are imported by five `.test.tsx` files and by no production module, so
  what a judge sees comes from `scenario.py` over the wire — and because the one
  case the drift might have masked is independently pinned by the hand-built
  `TrackerItem` literal at `TrackerRow.test.tsx:16-30`. Recorded honestly: this
  is a criterion that decayed rather than a nicety never met, since CP-053 flipped
  these fixtures to "server truth" precisely so the conformance test would stop
  masking drift. *Trigger:* the next web component or test written against them —
  refresh the fixtures first, or write against fiction.
- **`TrackerDashboard`'s `handleNotify` is unpinned.** D62, from CP-054's review.
  Gutting `TrackerDashboard.tsx:75-79` alone leaves all 50 tests green.
  **Verified correct by reading, unpinned by testing — both are true.** Those
  four lines are a literal-for-literal twin of `handleDraftEmail` (same
  `postTrackerAction`, same `replaceItem` update, same `catch`), and both ends
  are already pinned: `client.test.ts:130-133` for the request body,
  `TrackerRow.test.tsx:108-111` for the button reaching `onNotify`. So the demo
  will not break, and a future edit to those four lines would not be caught. One
  container test mirroring the draft-email one closes it. *Trigger:* any edit to
  that container, or notify entering a demo script.
- ~~**`index.css` styles the two badges through their `data-testid` hooks.**~~
  **CLOSED 2026-09-02 by the design pass (D63), one day after it was filed.**
  Its trigger — "the next edit to either atom or to `index.css`" — fired exactly
  as written, and the fix landed as the entry prescribed: `StateBadge` and
  `RiskBadge` now carry `state-badge state-badge--{state}` and
  `risk-badge risk-badge--{risk}`, and `index.css` selects those classes.
  Verified this turn rather than taken on report: the only occurrence of
  `data-testid` left in the stylesheet is a comment at `index.css:4` recording
  the rule and citing D61 by number. The original entry, kept for its evidence:
  `index.css:129-130` selected `[data-testid="risk-badge"]` and
  `[data-testid="state-badge"]` because the atoms exposed no class name — a real
  cross-coupling rather than a preference, since a test-only refactor renaming a
  `data-testid`, which anyone would treat as safe, silently broke the demo's
  appearance. It was deferred because the fix meant editing two `DONE` atoms.
- **The `as` cast cannot see a missing or renamed fixture field, and
  `fixtures.test.ts` contradicts itself about it.** D58, from CP-053's review.
  Deleting `project_id` from `tracker.json[0]`, or renaming it to `projectId`,
  leaves typecheck and the suite green — the cast catches a wrong *type*, never a
  missing or renamed key, and tracker items have no counterpart to the analyze
  fixture's `Object.keys` assertion. That is the residual hole in the masking
  CP-053 exists to close. In the same file, the comment at `fixtures.test.ts:19`
  still claims the cast catches "a renamed or missing field at any depth",
  fifteen lines above a newer comment correctly saying it performs no
  excess-property check. Fix the assertion and the comment together. *Trigger:*
  the next fixture edit — and D60's refresh is one, so these two land well in one
  turn.
- **The environment trio is atomic in one direction only.** D56, from CP-052's
  review. Removing `CLEARCUT_MODE` from `OPTIONAL_ENV_VARS` while both documents
  keep it reddens three tests; removing it from `.env.example` while
  `OPTIONAL_ENV_VARS` keeps it stays green. CP-052's criterion claimed "any
  intermediate commit is a red tree", which holds for one ordering rather than
  both. Deferred because the variable is optional by construction — losing it
  from `.env.example` yields live mode by default, which fails loudly on
  `GOOGLE_CLOUD_PROJECT` rather than quietly. *Trigger:* the next variable added
  to `OPTIONAL_ENV_VARS`, or any edit to `.env.example`.
- **`README.md:47` names a bare `python` in the live-mode command.** D57, from
  CP-052's review, and the cheapest item here. Attempt 2 fixed line 18 to
  `./.venv/bin/python` for mock mode and left the live-mode paragraph resolving
  to nothing in a shell where the virtualenv was never activated; its reviewer
  ruled it outside that checkpoint's criteria rather than acceptable. Deferred on
  which reader it breaks: live mode needs twelve credentials and the demo runs
  mocked, so nobody walks it before the deadline. Reuse attempt 1's own wording —
  do not leave a boot command that only works in an already-activated shell.
  *Trigger:* the next README edit, or anyone actually attempting live mode.

**Placed 2026-09-02: two deferrals from the user-ordered design pass (D64–D65).**

`349da37` was delegated-direct work on a direct user order, not a checkpoint —
D63 records why that is legitimate and why it is written down. Its review left
two non-blocking findings. It also **closed D61 above**, whose trigger fired one
day after it was filed.

- **A 490-line hand-maintained stylesheet is checked by nothing.** D65, from the
  design pass's review, and the one with teeth. Verified this turn:
  `.claude/init.sh` names no CSS gate and `web/package.json` declares no CSS
  tooling, so of the six gates `check()` runs — ruff, ruff format, mypy, pytest,
  `npm run typecheck`, `npm test` — not one reads a stylesheet. `web/src/index.css`
  grew from roughly 138 lines to 490 in that single commit. This is not a lint
  preference: the review's one blocking finding was a **dead class**, exactly the
  defect a CSS gate catches mechanically and human review catches by diligence.
  Diligence won this time; the gap that let it reach review is still open. Same
  reasoning as D44, where `init.sh check` running zero frontend gates is how
  CP-053's contract drift survived every earlier review. The fix is stylelint, or
  prettier over `*.css`, wired into `check()` beside the two npm gates.
  *Trigger:* the next `index.css` edit — add the gate before changing a rule, not
  after.
- **`TrackerRow` lost its label colons in the `dl` restructure.** D64, from the
  same review, raised as optional and ranked low here on purpose. A `dl` grid
  already separates term from description both visually and structurally, so the
  colon is redundant punctuation in the new layout rather than a dropped cue.
  What would change that is evidence rather than taste. *Trigger:* anyone
  reporting that the flat labels read ambiguously — at which point
  `dt::after { content: ":" }` restores them in one declaration, with no markup
  change.

---

## Archive

Moved to `.claude/ARCHIVE.md` on 2026-09-05. Closed checkpoints and their
reviewer evidence live there; nothing in it is dispatchable, and the loop
never needs to read it.
