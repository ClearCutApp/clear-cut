# ClearCut Software Design Document

## 1. Scope and constraints

ClearCut is a 9-day hackathon build (today is August 29, 2026; Agentic Cinema
closes September 7, 2026). This document is the design contract the leader
decomposes into `CHECKPOINTS.md`. `AGENT.md` governs how the code is written:
three layers with dependencies pointing inward, ports only at real I/O
boundaries, no abstraction from §4's banned list, tests before code.

The build supersedes the architecture in
`resources/Technical-Architecture-and-Hackathon-Framing.md`. Two of that
document's ideas survive in concrete form here: the Legal Inference Engine
becomes the `SceneExtractor` port, and the Territorial Actionability Engine
becomes the `LegalGrounding` and `RightsResearch` ports. Its Dynamic
Scalability Module was named but never specified as an algorithm; section 4.3
below defines it as content-hash scene diffing.

Out of scope for the hackathon: computer vision over attached images, audio
fingerprinting, auto-sending any legal correspondence (drafts only, a human
sends), and jurisdictions beyond the ten in the rights-mapping document.

## 2. Domain model

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
| `LoreStore` | `adapters/bigquery/lore_store.py`, BigQueryVectorStore from langchain-google-community | BigQuery reads and writes; the store auto-creates its dataset and table and brute-force scans under 5,000 rows |
| `TrackerStore` | `adapters/clickhouse/tracker.py`, ClickHouse Cloud | Inserts and reads over the ClickHouse HTTPS interface; versioned rows in a ReplacingMergeTree keyed by `item_id`; also owns the `script_versions` table, the per-version scene hash sets EvaluateDelta reads |
| `Notifier` | `adapters/notify/webhook.py`, outbound webhook | HTTP POST to the configured webhook on producer-triggered notification actions and automatically on delta regressions |

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
point:

- `AnalyzeScript(ingestion, extractor, grounding, research, lore, tracker)`:
  the full pipeline of section 4.1. Returns an AnalysisReport (script,
  findings, tracker items).
- `EvaluateDelta(ingestion, extractor, grounding, research, lore, tracker)`:
  the incremental path of section 4.3.
- `ResolveFinding(tracker, notifier)`: state transitions and action triggers
  on one tracker item.
- `AnswerProjectQuestion(lore, grounding, tracker)`: the Q&A path of section
  4.2, backed by gemini-3.1-flash-lite over retrieved context. It reads
  tracker state for questions about territory blockers and outreach status.

If gemini-3.1-pro-preview becomes allowlisted, it replaces flash only inside
the extractor adapter; no other file changes.

## 4. API surface

Flask serves JSON only. Routes live in `adapters/http/` and do nothing beyond
mapping HTTP to use-case input and output.

The AnalyzeScript use case realizes the agent topology described in
`plan/agentic-workflow.md` by coordinating the adapter calls in-process;
nothing deploys as a separate orchestrator agent. The project Q&A agent is
the one component hosted on Google Cloud Agent Builder, with the Vertex AI
Search data store attached as its grounding source.

### 4.1 POST /api/analyze (the pipeline)

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
     findings skip the RightsResearch lookup.
6. **Embed.** Each scene is written to the LoreStore so later episodes can
   retrieve it as history.
7. **Track.** Every finding becomes a TrackerItem at BLOCKED, written to
   ClickHouse with `version = 1`.
8. **Respond.** The JSON response carries the script metadata, scenes,
   findings with citations, and tracker items. The SPA needs no second call
   to render the first view.

### 4.2 The remaining endpoints

- `POST /api/projects`: create a project with a jurisdiction.
- `POST /api/projects/{id}/bible`: upload bible documents; the backend
  splits them into BibleFacts and indexes them in the LoreStore.
- `GET /api/scripts/{script_id}`: scenes plus findings, the ScriptView
  payload.
- `GET /api/tracker?project_id=`: tracker items with current state, the
  TrackerDashboard payload.
- `PATCH /api/tracker/{item_id}`: state transition; writes a new versioned
  row.
- `POST /api/tracker/{item_id}/actions`: body `{"action": "draft_email" |
  "generate_document" | "stakeholder_link" | "notify"}`. Draft email fills
  the outreach template from the rights-mapping document with the finding's
  data and stores it on the item for the producer to copy and send; the
  system never sends it. `generate_document` drafts the required document
  named on the finding. `stakeholder_link` returns the rights holder's
  registry or contact link, resolved by RightsResearch and stored on the
  tracker item; the dashboard opens it. `notify` calls the Notifier.
- `POST /api/question`: body `{project_id, question}`; AnswerProjectQuestion
  retrieves bible facts and scene history from the LoreStore, adds
  LegalGrounding context when the question names a legal topic, and answers
  with citations.

### 4.3 EvaluateDelta (incremental re-analysis)

Triggered when `POST /api/analyze` receives a project that already has a
script version. After step 2 (parse plus hash), the use case runs
`diff_scenes` against the stored previous version:

- UNCHANGED scenes are skipped entirely. Findings, embeddings, and tracker
  items survive as they are.
- ADDED and CHANGED scenes are re-extracted, re-enriched, and re-embedded
  (the old rows for a CHANGED scene are deleted from the LoreStore first).
- REMOVED scenes keep their open tracker items with a note; nothing is
  deleted, because a cut scene can return in v3.
- Carry-forward matches by asset identity: a re-extracted finding that names
  the same asset (same category plus normalized asset name) as an existing
  one keeps its `finding_id` and its tracker state, even when the asset moved
  to a different scene. Findings and permissions on unchanged scenes carry
  forward as they are. A CHANGED scene whose tracker item was CLEARED keeps
  its state but gets `needs_review` set to true and a notification, matching
  ADR 0007: the clearance is neither silently kept nor dropped. Only
  genuinely new assets get new EVT ids and start at BLOCKED.

This is the concrete algorithm behind what the legacy architecture document
called the Dynamic Scalability Module.

## 5. Frontend separation of concerns

The SPA lives in `web/` at the repo root, outside `src/clearcut/`, built with
React, Vite, and Tailwind. The backend never renders a template; one Cloud Run
service serves the JSON API and the static `web/` build output.

Structure follows atomic design: atoms (RiskBadge, StateBadge, CitationLink),
molecules (FindingCard, SceneHeader, TrackerRow), organisms (FindingsOverlay,
TrackerTable, ChatPanel), then pages. Container components own data fetching
and state; presentational components receive props and stay pure. One typed
API client module, `web/src/api/client.ts`, is the single point of contact
with the backend; every request/response type in it mirrors the JSON shapes of
section 4, so a backend shape change breaks the frontend build instead of a
demo.

Three surfaces:

- **ScriptView** consumes `GET /api/scripts/{id}` and renders the screenplay
  text with findings overlaid inline at their scenes, each finding showing
  category, risk, and citations.
- **TrackerDashboard** consumes `GET /api/tracker`, renders items grouped by
  state (BLOCKED, IN_PROGRESS, CLEARED), and issues `PATCH` for transitions
  and `POST .../actions` for draft-email, generate-document,
  stakeholder-link, and notify triggers.
- **ProjectQA** consumes `POST /api/question` and renders the conversational
  panel with the answer's citations linked.

## 6. Observability

Grafana Cloud receives traces and metrics over OTLP. The OpenTelemetry SDK is
configured once in `composition.py` (tracer provider, meter provider, OTLP
exporter with the Grafana Cloud endpoint and token from environment
variables). Adapters create the spans around their outbound calls. `domain/`
and `application/` import nothing from OpenTelemetry.

One trace per `/api/analyze` request, with one span per pipeline stage:
`ingest`, `extract`, `ground`, `research`, `track`. Span attributes carry
`script_id`, `scene_number` where applicable, the Gemini model name, and token
counts read from each response's usage metadata.

Metrics:

- `clearcut_stage_latency_ms`: histogram, labeled by stage.
- `clearcut_gemini_tokens_total`: counter, labeled by model
  (gemini-3.7-flash vs gemini-3.1-flash-lite), split into prompt and output.
- `clearcut_findings_total`: counter, labeled by risk_level and category.
- `clearcut_tracker_items`: gauge, labeled by state, refreshed on every
  tracker write.

The demo Grafana dashboard shows stage latency, token spend per model, and
the findings-by-severity and tracker-by-state breakdowns for the verification
run in section 8.

## 7. Delivery phases and dependency edges

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

## 8. Verification

Four checks, run in this order once their phases land:

a. **Ingestion (Phase 1).** Parse a real screenplay PDF. Assert the scene
   count against a manual count, and for 5 spot-checked scenes assert that
   `page_start` equals the page number printed on the PDF page where the
   slugline appears.

b. **Lore isolation (Phase 2).** Seed bible facts for two projects, A and B.
   Run VECTOR_SEARCH directly via `bq query` with the project filter for A
   and assert zero returned rows belong to B. This proves the metadata filter
   in SQL, outside our own code path.

c. **Grounding citations (Phase 3).** Query the data store with jurisdiction
   = "Argentina" and confirm the response carries citation URIs in
   groundingChunks, not only answer text. A grounded answer without a URI
   fails the check.

d. **End to end (Phase 4).** Analyze a planted script containing a Ferrari
   Testarossa (BRAND, trademark clearance), "Hotel California" playing on a
   radio (MUSIC_EXISTING, sync license), and one contradiction of a seeded
   bible fact (CONTINUITY). Assert all three findings surface with the
   correct page numbers, the tracker reads exactly 3 open items at BLOCKED,
   and the run produced a visible trace with the five stage spans and
   non-zero token metrics in the Grafana dashboard.
