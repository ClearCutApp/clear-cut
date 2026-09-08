> Historical reference. Recovery specification and workflow in `AGENTS.md` and
> `docs/recovery/` supersede conflicting instructions and completion claims.

# ClearCut Software Design Document

## Status of this document

This document is both the design contract and the current state of the build.
Every section carries markers saying how much of what it specifies actually
runs. Read this legend before the first marker.

**DONE** means integrated with the actual provider, with unit tests, defensive
tests, and live integration tests all green. All three kinds, against the real
service.

**WIP** means the code exists and its unit tests pass, but at least one of:
it has never run against the provider, its failure paths are untested, or no
live test covers it.

**MISSING** means there is no implementation, or an implementation nothing
calls.

Two rules keep the markers honest. Every marker names its evidence: a test
file, a gate result, or the specific absence. And a live test that passes
without credentials is not evidence, because its only honest outcomes are pass
with credentials or skip without them.

**Aggregate as of 2026-09-05.** The domain layer is DONE. The adapter tier has
contacted every service it wraps: `clearcut-hack` exists, both planes are
provisioned, and the end-to-end check of section 8(d) passed live on 2026-09-04
in 870 seconds. What is now WIP is the product around the engine. One of six
screens is complete, findings are never persisted, and analysis blocks its HTTP
request for twelve to twenty minutes. Section 9 carries the counts and the gate
numbers.

**The goal changed on 2026-09-05.** This document was written to grade a
hackathon submission judged on one analyze call. ClearCut is now built as a web
application a producer uses. ADR 0012 partitions the API into six bounded
contexts and reinstates the three endpoints ADR 0011 cut; ADR 0013 makes
analysis a job resource; ADR 0014 makes findings durable and fixes a ClickHouse
key that silently destroys one project's data when two projects mint the same
identifier; ADR 0015 computes highlight offsets in the domain. Where this
document and those records disagree, the records are newer.

**On the markers themselves.** Between 2026-09-03 and 2026-09-05 three
summaries in this file said the section 8(d) check had never run while section
8(d) recorded its own passing run with a timing. The cause was not carelessness
about one number: `./.claude/init.sh live` reported green while executing
nothing, so for two days "it passed" and "it never ran" printed identically.
The gate is fixed. The markers below have been re-graded against it.

**Why this document grew a status column.** Fifty-four checkpoints closed
against it with 477 passing tests while no service had been called even once.
Two identifier bugs certain to fail on the first real call sat in the branch
throughout, invisible to every test. A design document that cannot separate
"specified" from "working" is what allowed that. Section 7 already demanded
real services in every one of its five exit criteria; nothing ever checked.

## 1. Scope and constraints

ClearCut is a 9-day hackathon build, now at day 6 of 9: Agentic Cinema closes
September 7, 2026, four days from this revision. This document is the design
contract the leader decomposes into `CHECKPOINTS.md`. `AGENT.md` governs how
the code is written: three layers with dependencies pointing inward, ports only
at real I/O boundaries, no abstraction from §4's banned list, tests before
code, and since D66 a live test for every adapter.

The build supersedes the architecture in
`docs/resources/Technical-Architecture-and-Hackathon-Framing.md`. Two of that
document's ideas survive in concrete form here: the Legal Inference Engine
becomes the `SceneExtractor` port, and the Territorial Actionability Engine
becomes the `LegalGrounding` and `RightsResearch` ports. Its Dynamic
Scalability Module was named but never specified as an algorithm; section 4.3
below defines it as content-hash scene diffing.

Out of scope for the hackathon: computer vision over attached images, audio
fingerprinting, auto-sending any legal correspondence (drafts only, a human
sends), and jurisdictions beyond the ten in the rights-mapping document. These
four are decisions, not gaps. No status marker applies to them and none should
be added later.

## 2. Domain model

**Status: DONE.** Eight modules, all pure.
`tests/unit/test_layer_boundaries.py:133` proves mechanically that they import
only the stdlib or each other, so "integrated with the actual provider" is
vacuous here and the bar reduces to tests. Those are green: 79 test functions
across `tests/unit/domain/`, with rejection paths on every dataclass that has
an invariant. This is the only section of this document that qualifies.

Everything in this section lives in `src/clearcut/domain/` as plain
dataclasses. No I/O, no third-party imports, stdlib only. Time and identifiers
arrive as arguments.

**Script.** One uploaded screenplay version. Fields: `script_id`,
`project_id`, `version` (integer, increments per upload), `gcs_uri`,
`jurisdiction_code`, `scenes` (ordered list of Scene).

**Scene.** The unit of analysis, chunking, and hashing. Fields: `number`
(screenplay scene number), `heading` (the slugline, e.g. `EXT. BUENOS AIRES
STREET - NIGHT`), `page_start` and `page_end` (from Document AI page anchors),
`text`, `content_hash` (SHA-256 of the text normalized to lowercase with
collapsed whitespace). The hash is the identity used by delta evaluation;
`number` plus `heading` is the join key across versions.

**Finding.** One detected clearance event, the EVT-001 shape from the
rights-mapping matrix. Fields: `finding_id` (EVT-NNN, sequential per project,
assigned at first detection and stable across script versions), `scene_number`,
`page`, `raw_text` (the quoted script fragment), `category`, `ner_label`,
`risk_level` (LOW, MEDIUM, HIGH, CRITICAL), `required_document` (e.g. "Sync
License + Master License"), `citations` (list of Citation: `uri`, `title`,
`snippet`), `contradicts` (optional reference to a bible fact, for continuity
findings).

`category` takes one of eight values. Six come from the rights-mapping
document: INDUSTRIAL_PROPERTY, COPYRIGHT_WORKS, PERSONALITY_IMAGE,
INTEGRATED_VISUAL, LOCATIONS_PERMITS, SPECIAL_SYMBOLS. Two come from the
Project Bible audit: CONTINUITY (lore contradictions) and POLICY (tone or
rating violations). Bible findings carry no `ner_label`.

`ner_label` uses the eleven-tag taxonomy verbatim: BRAND, MUSIC_EXISTING,
MUSIC_ORIGINAL, ART_LIT, MEDIA_AV, TALENT_CHARACTER, REAL_PERSON, PROPS_DESIGN,
LOCATION_PRIV, LOCATION_PUB, SPECIAL_SYMBOL. The label-to-category mapping is a
pure function in `domain/taxonomy.py`: BRAND maps to INDUSTRIAL_PROPERTY;
MUSIC_EXISTING, MUSIC_ORIGINAL, ART_LIT, and MEDIA_AV map to COPYRIGHT_WORKS;
TALENT_CHARACTER and REAL_PERSON map to PERSONALITY_IMAGE; PROPS_DESIGN maps to
INTEGRATED_VISUAL; LOCATION_PRIV and LOCATION_PUB map to LOCATIONS_PERMITS;
SPECIAL_SYMBOL maps to SPECIAL_SYMBOLS.

**Jurisdiction.** A value object: `code` (ISO 3166-1 alpha-2, e.g. `AR`),
`display_name`, `corpus_prefix` (the folder under `gs://clearcut-legal-corpus/`,
e.g. `argentina/`). The ten supported values mirror the rights-mapping
document: Argentina, United States, Spain, Mexico, Canada, France, United
Kingdom, India, Brazil, South Korea.

**TrackerItem.** The actionable side of a Finding. Fields: `item_id`,
`finding_id`, `scene_numbers` (every scene where the asset appears, filled by
the dedupe step of section 4.1), `state` (BLOCKED, IN_PROGRESS, CLEARED),
`needs_review` (boolean, default false; set when a CLEARED item's scene
changes, section 4.3), `required_document`, `contact` (rights-holder name and
email when RightsResearch resolved one), `litigation_posture` (the rights
holder's litigation record as RightsResearch reported it), `draft_email`
(optional, produced on request, never sent by the system), `note`,
`updated_at`, `version` (monotonic, for ClickHouse latest-wins reads).
The percentages the source matrix expresses as 0/50/100 are presentation only;
the domain stores the state words. Every state transition is legal in both
directions (a producer can reopen a CLEARED item), and each transition writes
a new versioned row rather than mutating the old one.

**ProjectBible.** The project knowledge base: `project_id` and a list of
BibleFact entries (`fact_id`, `kind` being LORE or POLICY, `text`, `source`
such as "Bible p. 12" or "Episode 1, p. 4"). Facts are the retrieval unit the
LoreStore indexes.

**SceneDelta.** The output of comparing two script versions: `scene_number`,
`heading`, `kind` (ADDED, CHANGED, REMOVED, UNCHANGED), `old_hash`,
`new_hash`. Computed by a pure function `diff_scenes(old: list[Scene], new:
list[Scene]) -> list[SceneDelta]` that joins on `number` plus `heading` and
compares hashes.

**Evidence per module.**

| Module | Tests | Rejection paths proven |
|---|---|---|
| `jurisdiction.py` | `test_jurisdiction.py`, 5 | unknown code raises `UnknownJurisdiction`, not `KeyError` |
| `script.py` | `test_script.py`, 10 | version below one, scene numbers not strictly increasing, scenes out of order |
| `finding.py` | `test_finding.py`, 9 | CONTINUITY or POLICY finding carrying a `ner_label` |
| `taxonomy.py` | `test_taxonomy.py`, 3 | a value that is not a `NerLabel` |
| `bible.py` | `test_bible.py`, 6 | blank text, blank source, duplicate `fact_id` |
| `dedupe.py` | `test_dedupe.py`, 9 | empty input returns empty; the function cannot otherwise fail |
| `delta.py` | `test_delta.py`, 9 | duplicate join key within one version, named in the error |
| `tracker.py` | `test_tracker.py`, 28 | version below one, empty `scene_numbers`, blank `project_id`, blank draft, blank note |
| `errors.py` | via `test_error_translation.py`, 12 | four base types, each catchable as itself |

## 3. Ports, adapters, and use cases

Ports are `typing.Protocol` classes declared in `src/clearcut/application/`.
Each port exists because it crosses a network boundary; none wraps in-process
code, per `AGENT.md` §4. `composition.py` is the single wiring point.

| Port | Adapter (module, backing service) | Real I/O boundary that justifies it |
|---|---|---|
| `ScriptIngestion` | `adapters/gcp/document_ai.py`, Google Document AI | HTTPS call to the Document AI processor; reads the PDF from GCS; returns scenes with page anchors |
| `SceneExtractor` | `adapters/gemini/extractor.py`, gemini-3.7-flash | One Gemini API call per batch of up to eight scenes; `response_schema` pinned to the six-category finding shape; `thinking_level` set explicitly per call; temperature left at the default 1.0 because lowering it degrades Gemini 3 output |
| `RightsResearch` | `adapters/parallel/research.py`, Parallel Task API | HTTPS call that searches the live web for the rights holder, a contact address, litigation posture, and per-claim confidence (ASCAP/BMI Songview, SADAIC, WIPO Global Brand Database and peers) |
| `LegalGrounding` | `adapters/gcp/vertex_search.py`, Vertex AI Search | Query against the one data store built over `gs://clearcut-legal-corpus/`, filtered on the `jurisdiction` metadata field; returns grounded text plus `groundingMetadata` (groundingChunks and groundingSupports) as citations |
| `WebGrounding` | `adapters/parallel/search.py`, Parallel Search API | One HTTPS POST to `/v1/search` in `fast` mode, searching the live web for a legal question the licensed corpus could not cite; ranks government and intergovernmental hosts above the rest, caps at three, and quotes their excerpts as citations. Separate from `LegalGrounding` because it makes a weaker claim from a different boundary, and named `search` rather than `ground` so neither can be substituted for the other by accident |
| `ContinuityCheck` | `adapters/gemini/continuity.py`, gemini-3.1-flash-lite | One call per scene comparing the scene against retrieved bible facts; emits a CONTINUITY or POLICY finding on contradiction, or nothing. Called from step 5 of section 4.1 |
| `LoreStore` | `adapters/bigquery/lore_store.py`, BigQueryVectorStore from langchain-google-community | BigQuery reads and writes; the store auto-creates its dataset and table and brute-force scans under 5,000 rows |
| `TrackerStore` | `adapters/clickhouse/tracker.py`, ClickHouse Cloud | Inserts and reads over the ClickHouse HTTPS interface; versioned rows in a ReplacingMergeTree keyed by `item_id`; also owns the `script_versions` table, the per-version scene hash sets EvaluateDelta reads |
| `Notifier` | `adapters/notify/webhook.py`, outbound webhook | HTTP POST to the configured webhook on producer-triggered notification actions and automatically on delta regressions |

`ContinuityCheck` was absent from this table until 2026-09-03, although
`application/ports.py:128` has always declared it and `composition.py` has
always wired it. It is also the only adapter emitting neither a span nor a
metric, so it was invisible in the design and invisible in the trace at the
same time.

**Status per port.** Every one is WIP. None has run against its provider,
because the project holding those providers does not exist.

| Port | State | Unit | Defensive | Live | What stands between it and DONE |
|---|---|---|---|---|---|
| `ScriptIngestion` | WIP | 13 tests, hand-written client fake | transport error, no slugline, empty text segments, no pages | 1 test, skipped | Provisioning only. Coverage is otherwise complete |
| `LoreStore` | WIP | 10 tests, hand-written store and embedder fakes | blank project id, store raising on both read and write, project isolation | 2 tests, skipped | Provisioning, plus it emits no span and no metric |
| `TrackerStore` | WIP | 23 tests, hand-written client fake raising a real `DatabaseError` | all five methods wrapped, unknown item, empty project, absent script version | 3 tests, skipped | Provisioning. Only `save` is instrumented; the four read siblings are silent |
| `RightsResearch` | WIP | 14 tests over `httpx.MockTransport` | non-2xx, read timeout, connect error, unreadable 2xx body, uncited claims dropped, unknown confidence | 1 test, skipped | Provisioning. A 2xx the SDK could not build a `TaskRunResult` from used to cross the port as an `AttributeError` (500) or, worse, as a `NoRightsHolderFound` the use case swallows; the client now validates strictly and both arrive as `ResearchUnavailable` (502) |
| `LegalGrounding` | WIP | 6 tests, hand-written client fake | blank prefix, response without grounding chunks | 2 tests, skipped | The SDK call has no `try/except`. A Vertex 503 returns 500, not 502 |
| `WebGrounding` | WIP | 17 tests over `httpx.MockTransport` | non-2xx, connect error, unreadable 2xx body, empty excerpts dropped, non-http URL dropped, nothing usable at all | 1 test, skipped | Provisioning only. The call shape (`fast` mode, the jurisdiction in the objective, keyword-length queries) is asserted from the request body, which is the only place it is provable |
| `SceneExtractor` | WIP | 9 tests, hand-written client fake | unrecognized `ner_label`, empty scene list | 1 test, skipped | The SDK call has no `try/except`. Malformed JSON or a hallucinated scene number returns 500 |
| `Notifier` | WIP | 7 tests over `httpx.MockTransport` | blank URL, non-2xx, connect error, read timeout | none | No live test exists, although `NOTIFY_WEBHOOK_URL` is a required live variable |
| `ContinuityCheck` | WIP | 9 tests, hand-written client fake | category outside CONTINUITY/POLICY, empty facts short-circuit | none | Fails every axis: no live test, no span, no metric, no `try/except`. Called once per scene |

The three unguarded adapters are worth stating plainly, because the symptom is
misleading. `VertexSearchGrounding._ground`, `GeminiSceneExtractor._extract_batch`
and `GeminiContinuityCheck.check` all call the SDK bare. A `google.genai`
`APIError`, a `JSONDecodeError` from a non-JSON response, or a `KeyError` from
a model inventing a scene number reaches `routes.py:106`'s generic handler and
becomes a 500 reading "internal error". An upstream outage is reported to the
producer as a ClearCut bug.

Notes on the two retrieval adapters, since both hide sharp edges:

- BigQueryVectorStore does not chunk. Scene-level chunking is our design: one
  row per scene and one row per BibleFact, embedded through an injected
  `VertexAIEmbeddings` instance (text-embedding-005), which is the single
  place to swap the embedder. Metadata columns are `project_id`, `kind`
  (`scene` or `bible_fact`), `episode`, `scene_number`, `page`, and
  `content_hash`, all strings or integers; we never filter on floats. Queries
  filter on `project_id` with the dict filter first, and drop to a raw SQL
  filter string when dict semantics fight us.
- LegalGrounding uses one Vertex AI Search data store, not one per country.
  The corpus bucket has one prefix per jurisdiction and each document carries
  a `jurisdiction` metadata field; the adapter filters on it at query time.

Application-layer use cases, each one behaviour with a single `execute` entry
point. The two pipeline use cases take `continuity` as a collaborator, which
earlier revisions of this section omitted:

- `AnalyzeScript(ingestion, extractor, grounding, research, lore, tracker,
  continuity)`: the full pipeline of section 4.1. Returns an AnalysisReport
  (script, findings, tracker items).
- `EvaluateDelta(ingestion, extractor, grounding, research, lore, tracker,
  continuity, notifier)`: the incremental path of section 4.3.
- `ResolveFinding(tracker, notifier)`: state transitions and action triggers
  on one tracker item.
- `AnswerProjectQuestion(lore, grounding, tracker)`: the Q&A path of section
  4.2, backed by gemini-3.1-flash-lite over retrieved context. It reads
  tracker state for questions about territory blockers and outreach status.

**Status per use case.** These have no provider of their own, so their bar is
unit and defensive coverage over fake ports, plus whatever the ports beneath
them can prove.

| Use case | State | Evidence |
|---|---|---|
| `AnalyzeScript` | WIP | 27 tests. The strongest defensive coverage in the codebase: enrichment degradation on `EnrichmentMissing`, propagation on `SourceUnavailable`, a stray `TypeError` proven to propagate rather than be swallowed, and port call order asserted against section 4.1 |
| `AnswerProjectQuestion` | WIP | 24 tests, including dedicated raising fakes. A tracker outage propagates rather than reading as "nothing is blocked", which is the failure that would matter most |
| `ResolveFinding` | WIP | 12 tests. A notifier failure does not lose an already-saved transition |
| `ListTrackerItems` | WIP | 4 tests. A pass-through with an empty-result case |
| `EvaluateDelta` | WIP | 16 tests, and **not one in which any port raises**. Its two `except EnrichmentMissing` blocks are untested, where `AnalyzeScript` has six tests for the same construct. The largest module in the codebase at 408 lines |

If gemini-3.1-pro-preview becomes allowlisted, it replaces flash only inside
the extractor adapter; no other file changes. It is not allowlisted, so this
remains conditional rather than MISSING.

## 4. API surface

Flask serves JSON only. Routes live in `adapters/http/` and do nothing beyond
mapping HTTP to use-case input and output.

The AnalyzeScript use case realizes the agent topology described in
`docs/plan/agentic-workflow.md` by coordinating the adapter calls in-process;
nothing deploys as a separate orchestrator agent. The project Q&A agent is
the one component hosted on Google Cloud Agent Builder, with the Vertex AI
Search data store attached as its grounding source.

**Status: amended 2026-09-05. The contract moved to
`docs/api/openapi.yaml`,** which specifies 20 operations across six tags
(System, Projects, Scripts, Tracker, Bible, Questions) per ADR 0012. Eight are
served today. That file is the contract; this section describes the pipeline
behind the one operation that matters most and is no longer the route
inventory. Two shapes changed there and not yet here: script upload answers
**202** with a `Location` naming an analysis job (ADR 0013), and the tracker
action verb is replaced by `email-drafts` and `notifications` sub-resources.

**Historical status: eight routes specified, five built, and every path is now a
resource.** `POST /api/analyze` and `POST /api/question` were RPC verbs; they
and the tracker collection were renamed on 2026-09-03 so that every path names
a noun and every collection nests under its owner. `project_id` moved from the
body and query string into the path, which is the substantive half of the
change: a blank project is now a routing concern that never reaches a handler. `routes.py` carries five
`@bp.route` decorators. A sixth route, `GET /api/health`, exists and is
described below; it was added after this section was first written.

| Route | State | Evidence |
|---|---|---|
| `POST /api/projects/{id}/scripts` | WIP | Built. 39 tests in `test_routes.py`, the largest test file at 947 lines. Never called against live adapters |
| `GET /api/projects/{id}/tracker-items` | WIP | Built and tested, including the 400 and 502 paths |
| `PATCH /api/tracker-items/{item_id}` | WIP | Built and tested, including an invalid state naming the accepted values |
| `POST /api/tracker-items/{item_id}/actions` | WIP | Built for `draft_email` and `notify`. `generate_document` and `stakeholder_link` return 500 by decision, not by defect |
| `POST /api/projects/{id}/questions` | WIP | Built and tested, including blank project id and unknown jurisdiction |
| `GET /api/health` | WIP | Built. Reports the wired `CLEARCUT_MODE` so the SPA can say when it is serving planted data. 3 tests, one covering the SPA catch-all shadowing it |
| `POST /api/projects` | MISSING | No route, no test |
| `POST /api/projects/{id}/bible` | MISSING | No route, no test. Nothing else populates the LoreStore through the API |
| `GET /api/scripts/{script_id}` | MISSING | No route. ScriptView renders from the analyze response instead |

The bible upload is the consequential absence. Without it the LoreStore is
never filled through the API, so the CONTINUITY finding that section 8(d)
demands has no supported route by which to come into existence. The demo
scenario seeds it directly through the mock adapter instead.

Route-level error mapping is complete and tested: `RecordNotFound` to 404,
`SourceUnavailable` to 502, everything else to a 500 that leaks no internals.
Ten tests cover the three classes.

### 4.1 POST /api/projects/{id}/scripts (the pipeline)

**Status: WIP.** All eight steps are built and covered by unit tests over fake
ports. None has run against a real service.

Input: `project_id`, `jurisdiction_code`, and the screenplay PDF (multipart or
an existing GCS URI). Ordered flow:

1. **Upload.** The route streams the PDF to
   `gs://clearcut-scripts-intake/{project_id}/v{n}.pdf` and records a new
   Script with the next version number.
2. **Parse.** `ScriptIngestion` sends the PDF through Document AI and returns
   scenes with `page_start`/`page_end` taken from the processor's page
   anchors. The use case computes each scene's `content_hash`.
3. **Extract.** The use case groups scenes into batches of up to eight, and
   `SceneExtractor` sends each batch through one gemini-3.7-flash call with
   `response_schema` pinned to the finding shape over the six IP categories
   (category, ner_label, raw_text, risk_level, required_document). Pinning
   the schema, not only `response_mime_type`, is what makes the output parse
   every time. The eleven NER tags and the category mapping ride in the
   system instruction with few-shot examples lifted from the rights-mapping
   document. The per-scene continuity check stays separate, on
   gemini-3.1-flash-lite via LoreStore retrieval (step 5).
4. **Dedupe.** Findings that refer to the same asset (same category plus
   normalized asset name) collapse into one finding carrying the list of
   scene numbers where the asset appears. A brand seen in 14 scenes yields
   one finding with 14 scene references, one enrichment pass, and later one
   tracker item.
5. **Enrich.** For each deduped finding, three lookups run:
   - `LegalGrounding` asks what the law of the selected jurisdiction says
     about this category of use and keeps the returned citations.
   - `RightsResearch` runs a Parallel Task API job and returns the rights
     holder, a contact address, the holder's litigation posture, and a
     per-claim confidence level. AnalyzeScript owns the confidence-to-risk
     rule (medium confidence raises the risk one step, low confidence marks
     the finding unverified), and the litigation posture lands on the
     tracker item.
   - `LoreStore` retrieves the nearest bible facts for the scene; a
     gemini-3.1-flash-lite call compares scene against facts and emits a
     CONTINUITY or POLICY finding when they contradict. flash-lite also
     writes the one-line scene summary stored as row metadata. These bible
     findings skip the RightsResearch and LegalGrounding lookups.
6. **Embed.** Each scene is written to the LoreStore so later episodes can
   retrieve it as history.
7. **Track.** Every finding becomes a TrackerItem at BLOCKED, written to
   ClickHouse with `version = 1`.
8. **Respond.** The JSON response carries the script metadata, scenes,
   findings with citations, and tracker items. The SPA needs no second call
   to render the first view.

Step 1 is the exception worth naming: no route accepts a multipart upload
today. The request carries an existing `gcs_uri`, and putting the PDF in the
bucket is a manual step. Steps 2 through 8 run as written.

### 4.2 The remaining endpoints

Status for each appears in the table at the head of section 4.

- `POST /api/projects`: create a project with a jurisdiction. **MISSING.**
- `POST /api/projects/{id}/bible`: upload bible documents; the backend
  splits them into BibleFacts and indexes them in the LoreStore. **MISSING.**
- `GET /api/scripts/{script_id}`: scenes plus findings, the ScriptView
  payload. **MISSING.**
- `GET /api/projects/{id}/tracker-items`: tracker items with current state, the
  TrackerDashboard payload. **WIP**, built.
- `PATCH /api/tracker-items/{item_id}`: state transition; writes a new versioned
  row. **WIP**, built.
- `POST /api/tracker-items/{item_id}/actions`: body `{"action": "draft_email" |
  "generate_document" | "stakeholder_link" | "notify"}`. Draft email fills
  the outreach template from the rights-mapping document with the finding's
  data and stores it on the item for the producer to copy and send; the
  system never sends it. `generate_document` drafts the required document
  named on the finding. `stakeholder_link` returns the rights holder's
  registry or contact link, resolved by RightsResearch and stored on the
  tracker item; the dashboard opens it. `notify` calls the Notifier.
  **WIP** for `draft_email` and `notify`; the other two are ruled to the
  Backlog and return 500 on purpose.
- `POST /api/projects/{id}/questions`: body `{project_id, question}`; AnswerProjectQuestion
  retrieves bible facts and scene history from the LoreStore, adds
  LegalGrounding context when the question names a legal topic, and answers
  with citations. When that corpus lookup cites nothing -- whether it raised
  `EnrichmentMissing` or returned prose with no citations behind it -- the
  question goes on to WebGrounding, and the live web answer is appended to
  whatever the corpus managed to say rather than replacing it. A cited corpus
  answer never spends that second call. A `SourceUnavailable` from the web
  search propagates to a 502 like every other adapter under D23, so a Parallel
  outage now fails a question that used to degrade to bible facts; that is
  deliberate and the reasoning is in `_web_answer`. **WIP**, built.
- `GET /api/health`: returns the wired `CLEARCUT_MODE`. **WIP**, built. Not
  part of the original design; added so the SPA can state when its data is a
  fixed sample rather than an analysis.

### 4.3 EvaluateDelta (incremental re-analysis)

**Status: WIP, with one MISSING inside it.** The path is built and routed:
`POST /api/projects/{id}/scripts` sends `version` greater than 1 here. Sixteen tests cover
it, and none of them makes a port raise.

Triggered when `POST /api/projects/{id}/scripts` receives a project that already has a
script version. After step 2 (parse plus hash), the use case runs
`diff_scenes` against the stored previous version:

- UNCHANGED scenes are skipped entirely. Findings, embeddings, and tracker
  items survive as they are.
- ADDED and CHANGED scenes are re-extracted, re-enriched, and re-embedded.
  The design calls for deleting a CHANGED scene's old LoreStore rows first.
  **That part is MISSING**, because the `LoreStore` port has no `delete`
  method, so a changed scene leaves a stale row that later retrieval can
  return as history. This is a known defect with a known cause, not an
  oversight.
- REMOVED scenes keep their open tracker items with a note; nothing is
  deleted, because a cut scene can return in v3.
- Carry-forward matches by scene: a re-extracted finding on a CHANGED scene
  takes over the `finding_id` and the tracker state of an existing item
  whose `scene_numbers` overlap the changed set. Matching on the asset
  itself would need a stored category and normalized text per finding, and
  no table holds them (section 6 of `infrastructure.md` defines none), so an
  asset that moves to a different scene arrives as a new item at BLOCKED
  while its old item stays open, flagged for re-review with a note.
  Findings and permissions on unchanged scenes carry forward as they are. A
  CHANGED scene whose tracker item was CLEARED keeps its state but gets
  `needs_review` set to true and a notification, matching ADR 0007: the
  clearance is neither silently kept nor dropped. New assets, and assets the
  pipeline can no longer tell apart from new ones, get new EVT ids and start
  at BLOCKED.

This is the concrete algorithm behind what the legacy architecture document
called the Dynamic Scalability Module.

## 5. Frontend separation of concerns

**Status: WIP.** Amended 2026-09-05. The description below was written for a
three-organism app and survived an entire UI rewrite unedited; it named a
`TrackerDashboard` component that no longer exists and a Tailwind dependency
that was never installed. What follows is what ships.

The SPA lives in `web/` at the repo root, outside `src/clearcut/`, built with
React 19 and Vite. Routing is `react-router` v8. Styling is vanilla CSS over
design tokens rather than Tailwind: the dependency was never added, and ADR
0009 is stale on that point. `web/src/index.css` is ten ordered `@import`
lines; the tokens live in `web/src/styles/tokens.css`. The backend never
renders a template; one Cloud Run service serves the JSON API and the static
`web/` build output.

The top-level layout is by responsibility, not by atomic tier:

- `shell/` — `AppShell`, `Sidebar`, `ProjectLayout`, `ProjectHeader`.
- `views/` — six routed screens: `ProjectsView`, `OverviewView`,
  `AnalyzeView`, `ScriptView`, `AskView`, `NotFoundView`. This is a pages
  layer under another name; the claim that there is none is no longer true.
- `features/` — `tracker/` and `item/`, each holding its own components and a
  pure `model.ts`. `TrackerDashboard` became
  `features/tracker/{TrackerTable,TrackerRow,TrackerFilters,TrackerStats}` over
  `model.ts`, which holds `trackerStats`, `groupByState`, `applyFilter` and
  `searchItems` as framework-free functions.
- `components/atoms/` — `RiskBadge`, `StateBadge`, `NeedsReviewBadge`,
  `FilterPill`, `EmptyState`, `ErrorNotice`, `ModeBanner`.
- `state/`, `theme/`, `styles/`, `testing/` — context and outcomes,
  enum-to-word maps, the ordered CSS partials, and the test harness.

`components/molecules/` and `components/organisms/` still hold four files that
nothing imports. They are the residue of the move to `features/`, and their CSS
classes are undefined, so they would render unstyled if mounted. They are
scheduled for deletion, not preservation.

Container and presentational stay split: `state/ProjectContext.tsx` owns every
call and every piece of server state, and views render what it hands them.
`state/outcome.ts` folds failures into an `Outcome<T>` so a view renders an
outcome instead of catching. One typed API client, `web/src/api/client.ts`, is
the single point of contact with the backend, and every type in it mirrors the
JSON shapes of section 4 so a backend change breaks the build rather than the
demo.

`web/src/architecture.test.ts` enforces six rules, three of which are worth
naming here because they shape how the UI is written:

- only `client.ts` may contain a quoted `/api/` path literal
- no file under `components/atoms/` may import from `src/api/`
- a CSS class defined in a partial whose block is already in use, but rendered
  by no non-test component, **fails the build**. Dead CSS is a test failure, so
  a component is written before its stylesheet.

`.stylelintrc.json` adds a fourth constraint with product consequences: no
`height` or `min-height` may be `100vh`, `100dvh`, `100svh` or `100lvh`. The
body scrolls; nothing locks to the viewport. A design that assumes an
inner-scrolling app shell cannot be ported literally.

Screen status, 2026-09-05:

- **OverviewView** is the only complete screen. It renders `TrackerStats`,
  `TrackerFilters` and `TrackerTable` grouped by state, with row selection
  opening a panel column.
- **ProjectsView** renders a heading and an empty state. It reads the
  `localStorage` recent-project list and does not render it, because there is
  no project resource to render.
- **AnalyzeView**, **ScriptView** and **AskView** are headings. `ScriptView`
  says honestly that it has nothing to show, because findings are not persisted
  and the analysis lives only in session.
- **ItemDetailPanelHost** renders an item id and a Close button.

`ProjectContext` implements `changeState`, `draftEmail`, `notify` and `ask`.
As of this revision **none of the four has a caller.** The logic is built and
nothing renders it; that gap is the bulk of the remaining UI work, and it is
smaller than it looks.

**On honesty.** The SPA contains no hardcoded findings; `web/src/fixtures/` is
imported by tests only, in 11 files, never by a component. What it renders in
`CLEARCUT_MODE=mock` is a fixed sample served by the backend, and `ModeBanner`
says so on the page. Sidebar entries with no backing resource are drawn
disabled rather than wired to invented data. The code was always honest; the
data was not, and nothing admitted it.

## 6. Observability

**Status: WIP.** Every span and metric this section specifies is emitted in
code. None has ever left the process: no Grafana Cloud stack exists,
`OTEL_EXPORTER_OTLP_ENDPOINT` is unset, and `composition.py:95` treats an
absent endpoint as "export nowhere". Spans are created and discarded.

Grafana Cloud receives traces and metrics over OTLP. The OpenTelemetry SDK is
configured once in `composition.py` (tracer provider, meter provider, OTLP
exporter with the Grafana Cloud endpoint and token from environment
variables). Adapters create the spans around their outbound calls. `domain/`
and `application/` import nothing from OpenTelemetry.

One trace per script-creation request, with one span per pipeline stage:
`ingest`, `extract`, `ground`, `research`, `track`. Span attributes carry
`script_id`, `scene_number` where applicable, the Gemini model name, and token
counts read from each response's usage metadata.

All five stages are instrumented. What this section never named as a stage, and
what is therefore invisible in a trace, is three adapters that each cross a real
network boundary: `ContinuityCheck`, `LoreStore`, and `Notifier` emit neither a
span nor a metric. On a 200-scene analysis the continuity calls and the vector
reads are the bulk of the wall clock, so a Grafana waterfall will
under-account for latency until they are instrumented.

Metrics:

- `clearcut_stage_latency_ms`: histogram, labeled by stage.
- `clearcut_gemini_tokens_total`: counter, labeled by model
  (gemini-3.7-flash vs gemini-3.1-flash-lite), split into prompt and output.
- `clearcut_findings_total`: counter, labeled by risk_level and category.
- `clearcut_tracker_items`: gauge, labeled by state, refreshed on every
  tracker write.

All four are emitted. One caveat on the evidence:
`tests/unit/test_observability.py` proves the five spans share one trace id
and the four metrics record their labels **in `CLEARCUT_MODE=mock`**, driving
the in-memory adapters. Each live adapter's instrumentation is proven
individually in its own test file, but no test runs the five live adapters
together, so nothing yet proves they share a trace.

The demo Grafana dashboard shows stage latency, token spend per model, and
the findings-by-severity and tracker-by-state breakdowns for the verification
run in section 8. **The dashboard is MISSING.** Section 8(d) asserts against
it.

**A retrieval finding, recorded here because it has no better home.** The
`clearcut-project-qa` engine was created at `SEARCH_TIER_STANDARD` with no
`searchAddOns`, which is what `infra/provision_retrieval_plane.sh` produces
when it sets no tier. At that tier the store matches terms rather than meaning.
The engine has since been patched to `SEARCH_TIER_ENTERPRISE` with
`SEARCH_ADD_ON_LLM`, and whether that alone fixes retrieval is **unverified**:
the change had not taken effect when the probes were re-run. Two things hold
either way. The provisioning script should set the tier explicitly rather than
inherit a default, and enterprise tier bills in a way standard does not.

## 7. Delivery phases and dependency edges

**Status: phase 4 met on 2026-09-04. Phases 1, 2 and 3 are met by tests that
now run; phase 5 is unproven against a real service.** Amended 2026-09-05.

The paragraph this replaces said no exit criterion had been met, and it stayed
there after one of them was. Read the correction carefully, because the reason
matters more than the row: until 2026-09-05 `./.claude/init.sh live` reported
green while executing nothing, so "the tests skip" and "the tests pass" produced
the same output. The gate has been fixed and the numbers below are the recorded
runs, attributed.

| Phase | Exit criterion, verbatim | Met |
|---|---|---|
| 1 Ingestion | "a test turns a real screenplay PDF into scenes with page anchors and raw findings JSON" | **No.** `tests/live/test_document_ai_live.py` is exactly this test and it skips: `CLEARCUT_LIVE_SCRIPT_GCS_URI` is set nowhere, so Document AI has never parsed a PDF from a cold start |
| 2 Lore | "seeded bible facts come back from a project-scoped similarity query" | Yes at `337bddd`. `tests/live/test_bigquery_lore_store_live.py` proves a scratch-id fact round-trips; it does not prove the seeder indexed the demo project, which is why CP-057 is still IN_REVIEW |
| 3 Grounding | "a jurisdiction-filtered query returns grounded text with groundingChunks" | Yes at `337bddd` |
| 4 Wiring | "the end-to-end check of section 8(d) passes" | **Yes, 2026-09-04.** `1 passed in 870.64s` — see section 8(d) |
| 5 Delta | "uploading v2 with one edited scene re-analyzes exactly that scene and preserves CLEARED items" | No. Proven in mock mode only |

The live tier at HEAD is **9 passed, 5 skipped, 0 failed of 14**, run through
the corrected gate on 2026-09-05 in 92 seconds. This supersedes the same day's
earlier reviewer run of 8 passed, 1 failed: the failure was
`tests/live/test_parallel_research_live.py` timing out in the Task API
long-poll, and it does not reproduce. Treat that one as transient rather than
as a regression against `337bddd`.

Every skip is a missing environment variable, and the tier names each one
rather than passing over it:

| Skipped test | Wants |
|---|---|
| `test_document_ai_live.py` | `CLEARCUT_LIVE_SCRIPT_GCS_URI` |
| `test_end_to_end_live.py` | `CLEARCUT_LIVE_SCRIPT_GCS_URI`, `NOTIFY_WEBHOOK_URL` |
| `test_grafana_receipt_live.py` (3 cases) | `GRAFANA_URL`, `GRAFANA_TOKEN` |

`CLEARCUT_LIVE_SCRIPT_GCS_URI` is required by two tests and is named in no
markdown file and no `.env.example` entry. `tests/unit/test_environment_contract.py`
parses `_required_env` call sites against `.env.example` and section 8 of
`infrastructure.md`, and it does not reach the live tier's own requirements, so
nothing catches the omission.

Five phases. The first three are independent verticals; the leader can assign
them to parallel implementers on day one.

- **Phase 1 (Ingestion).** GCS upload, the Document AI adapter, Scene and
  Script dataclasses, content hashing, and the SceneExtractor adapter with
  its pinned response_schema. Exit: a test turns a real screenplay PDF into
  scenes with page anchors and raw findings JSON.
- **Phase 2 (Lore).** ProjectBible and BibleFact dataclasses, the
  BigQueryVectorStore adapter with the metadata columns of section 3, bible
  ingestion, and the contradiction check. Exit: seeded bible facts come back
  from a project-scoped similarity query.
- **Phase 3 (Territorial grounding and rights research).** The
  `clearcut-legal-corpus` bucket layout (one prefix per jurisdiction), the
  Vertex AI Search data store with the jurisdiction metadata field, the
  LegalGrounding adapter returning citations, and the Parallel Task API
  adapter. Exit: a jurisdiction-filtered query returns grounded text with
  groundingChunks.
- **Phase 4 (Wiring).** The ClickHouse tracker schema and adapter, the
  AnalyzeScript / ResolveFinding / AnswerProjectQuestion use cases, all Flask
  routes, `composition.py`, OpenTelemetry setup, and the three SPA surfaces
  against the live API. Exit: the end-to-end check of section 8(d) passes.
- **Phase 5 (Incremental delta).** `diff_scenes`, EvaluateDelta, selective
  re-embedding, and finding carry-forward. Exit: uploading v2 with one edited
  scene re-analyzes exactly that scene and preserves CLEARED items.

Edges, explicitly: Phase 1 → Phase 4, Phase 2 → Phase 4, Phase 3 → Phase 4,
Phase 4 → Phase 5. No edge connects Phases 1, 2, and 3 to each other. The
`web/` scaffold and presentational components can start any time before Phase
4 against fixture JSON, since the typed client is the only integration point.

Each phase's code is written. What separates every one of them from DONE is the
same thing: the `clearcut-hack` project does not exist, so the tests that would
close them skip instead of running.

## 8. Verification

**Status: (d) DONE on 2026-09-04. (a), (b) and (c) MISSING.** Amended
2026-09-05. This header said all four had never been run while section 8(d)
below recorded its own passing run with a timing. The document that grades
everything else failed to re-grade itself.

Four checks, run in this order once their phases land:

a. **Ingestion (Phase 1).** Parse a real screenplay PDF. Assert the scene
   count against a manual count, and for 5 spot-checked scenes assert that
   `page_start` equals the page number printed on the PDF page where the
   slugline appears.
   **MISSING.** Blocked on the Document AI processor and a screenplay PDF in
   `gs://clearcut-scripts-intake`. The spot-check against printed page numbers
   is manual and has no test.

b. **Lore isolation (Phase 2).** Seed bible facts for two projects, A and B.
   Run VECTOR_SEARCH directly via `bq query` with the project filter for A
   and assert zero returned rows belong to B. This proves the metadata filter
   in SQL, outside our own code path.
   **MISSING.** Blocked on the BigQuery dataset. Note the deliberate design:
   this check runs outside our code, so the live test that proves the same
   filter from inside it does not replace this one.

c. **Grounding citations (Phase 3).** Query the data store with jurisdiction
   = "Argentina" and confirm the response carries citation URIs in
   groundingChunks, not only answer text. A grounded answer without a URI
   fails the check.
   **MISSING.** Blocked on the data store, and on the console-only step that
   marks `jurisdiction` Indexable. Skip that step and filtered queries return
   every jurisdiction with no error at all, so this check is the only thing
   standing between a Mexico script and Argentine statute.

d. **End to end (Phase 4).** Analyze a planted script containing a Ferrari
   Testarossa (BRAND, trademark clearance), "Hotel California" playing on a
   radio (MUSIC_EXISTING, sync license), and one contradiction of a seeded
   bible fact (CONTINUITY). Assert all three findings surface with the
   correct page numbers, the tracker reads exactly 3 open items at BLOCKED,
   and the run produced a visible trace with the five stage spans and
   non-zero token metrics in the Grafana dashboard.
   **DONE as of 2026-09-04.** `1 passed in 870.64s` — fourteen and a half
   minutes, driven through `POST /api/projects/{id}/scripts` so the five stage
   spans share the trace the route roots. All three planted findings surfaced,
   their pages read back as 3, 5 and 8 off the real PDF, every tracker item was
   `BLOCKED`, and `clearcut_gemini_tokens_total` was non-zero. This is the
   first assertion in the project's history that could only pass against real
   services.

   Getting there took four runs, and each failure was worth keeping. `tests/live/test_end_to_end_live.py` drives the real
   `_build_live_use_cases` graph, so it proves the wiring as well as the
   services. The Ferrari and "Hotel California" surfaced on the first attempt;
   the contradiction did not, because `infra/seed_project_bible.py` had been
   written and never run, so the continuity check had no fact to contradict.

   **"Exactly 3 open items" does not survive a real model.** That run also
   produced a fourth finding: a PERSONALITY_IMAGE location release on scene 8,
   off "LOLA's father walks through the front door" -- a person and a private
   house, which is exactly what a clearance extractor should notice. The live
   test therefore asserts each planted finding reached the tracker at BLOCKED
   rather than counting the total. Counting would test the model's restraint
   instead of the pipeline, and a finding the model was right to make would
   fail a check about wiring.

   **A third correction: the trace root lives in the route.** Run three reached
   the trace assertion with all five stage spans present and fifteen distinct
   trace ids. Driving `AnalyzeScript` directly leaves the stage spans with no
   parent, because the root `analyze` span is opened by the HTTP route. Run
   four goes through `create_app().test_client()` and gets one trace. That is a
   real constraint rather than a fact about this test: a batch job or a
   scheduled re-analysis would fragment the same way.

   One number worth carrying into the demo: a full live run takes **twelve to
   twenty minutes**, not the "first minute" `proposal.md` promises.

## 9. Status summary

### 9.1 Counts and gates

Amended 2026-09-05.

| Area | DONE | WIP | MISSING |
|---|---|---|---|
| Domain entities (§2) | 10 | 0 | 0 |
| Ports (§3) | 8 | 5 declared, unimplemented | 0 |
| Use cases (§3) | 5 | 0 | 11 |
| Endpoints (§4) | 8 served | 0 | 12 contracted |
| Frontend screens (§5) | 1 | 5 | 0 |
| Observability (§6) | 5 spans, 4 metrics | 0 | dashboard |
| Phases (§7) | 1 | 3 | 1 |
| Verification (§8) | 1 | 0 | 3 |

Domain entities went from eight to ten: `Project` and `ClearanceRollup` landed
with CP-061, and `AnalysisJob` with ADR 0013. The five new ports —
`ProjectStore`, `ScriptStore`, `FindingStore`, `AnalysisJobStore`,
`ScriptStorage` — are declared and have no adapter yet, which is a real state
and not a WIP one. The endpoint row now counts against `docs/api/openapi.yaml`,
which contracts 20 operations across six tags; eight are served today.

Gates as of 2026-09-05:

- `./.claude/init.sh check`: **7 passed, 0 failed** — ruff, ruff format,
  `mypy src tests infra main.py` over 125 source files, 628 backend cases,
  stylelint, `tsc --noEmit`, 185 frontend cases across 40 files. Stylelint is
  the seventh gate, added in `79aacb1`.
- `./.claude/init.sh live`: **9 passed, 5 skipped, 0 failed** of 14 in 92
  seconds, through the corrected gate. Every skip names the variable it wanted;
  see section 7. Before 2026-09-05 this command printed
  `1 passed, 0 failed` while executing nothing, because pytest exits zero when
  every test skips and the gate read only the exit code. It now requires a
  `N passed` in the summary and names an all-skipped run as a configuration
  gap. `tests/unit/infra/test_live_gate.py` holds all three decisions.

Submission checklist from `infrastructure.md` §11:

| Item | State |
|---|---|
| Public repo with Apache-2.0 LICENSE at root | DONE |
| Hosted Cloud Run URL, publicly reachable | DONE. Revision `clearcut-00005-sqx`, `us-central1`, verified serving both the API and the built SPA (CP-060) |
| Three-minute demo video | MISSING |
| Devpost form before 2026-09-07 | MISSING |
| Runtime proof that calls are real and not mocked | DONE for the analyze path. Section 8(d) passed live on 2026-09-04. The Grafana receipt that would prove it a second way is blocked on a credential (CP-058) |

**The shortest path, as written on 2026-09-03 and now largely walked.** The
provisioning below is done; `clearcut-hack` exists and both planes are up. The
four code rows it named are still open, and `ContinuityCheck`'s missing
instrumentation is the one that matters most: it is the most frequent Gemini
call in the system, once per scene from both use cases, and it emits neither a
span nor a token count.

One action moves more rows than any other: create the
`clearcut-hack` project and run `infra/provision_data_plane.sh` and
`infra/provision_retrieval_plane.sh`. That alone converts five ports, four
phases, and three of the four verification checks from blocked to runnable.
Four rows would still fail after it, and they are code, not configuration:
`ContinuityCheck`'s missing live test and instrumentation, `Notifier`'s missing
live test, `EvaluateDelta`'s untested failure paths, and the three unguarded
SDK calls that turn upstream outages into 500s.

### 9.2 Promised elsewhere, with no home in this document

These are capabilities `proposal.md`, `agentic-workflow.md`, or an ADR commits
to, which sections 1 through 8 never place. They are listed rather than
resolved: giving them a design would be a change to the design, and this
revision reports state. Each row names where the promise lives so a later
decision starts from the source.

| Promise | Stated in | Why it has no home here |
|---|---|---|
| Policy and ratings agent: age-rating, brand and sponsor rules, tone rules | `agentic-workflow.md` §2.3 | Mapped onto `SceneExtractor`, whose `response_schema` §3 pins to the six IP categories, with no retrieval input. It cannot emit POLICY findings as specified |
| Declared territories, plural | `proposal.md`, `agentic-workflow.md` §4 | `Script` carries one `jurisdiction_code` (§2). An Argentina-Mexico co-production cannot be expressed |
| Confidence gate below 0.7, escalation to counsel | `agentic-workflow.md` §8 | `Finding` has no confidence field and the tracker has no escalated state |
| Single project clearance percentage | `proposal.md` | §2 makes percentages presentation-only, and no endpoint or component returns a rollup |
| Token ceilings, 8,000 in and 1,500 out per scene | `agentic-workflow.md` §8 | No metric in §6 measures them |
| A grounding query the data store can actually match | nowhere | Probed live 2026-09-03. English `copyright` and `intellectual property law` each retrieve two documents; `Ferrari trademark clearance` and any natural-language question retrieve none. Retrieval matches terms, not meaning. §4.1 step 5 has `AnalyzeScript` ask `LegalGrounding` a sentence, and nothing shapes it into terms the corpus contains. See the §6 note |

One further gap in the coverage rather than the design:
`NoPreviousScriptVersion` lives in `application/`, so neither
`test_error_translation.py` nor the contract walk in `test_error_boundaries.py`
covers it. Both scan `clearcut.adapters`. Its raise is proven in
`test_evaluate_delta.py`.
