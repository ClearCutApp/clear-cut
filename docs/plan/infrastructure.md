# Infrastructure

Provisioning guide for ClearCut. A developer follows this top to bottom on day
one and ends with every external service reachable from a local `.env` and a
deployable Cloud Run service. Names, regions, and variable names here are the
ones the code expects; do not improvise alternatives.

## 1. Google Cloud project

Create a new project rather than reusing a personal one, so the hackathon
credits and the API quota live in a clean billing scope.

```bash
gcloud projects create clearcut-hack --name="ClearCut"
gcloud config set project clearcut-hack
```

Request the hackathon's $100 Google Cloud credits through the Devpost resource
page immediately after creating the project. Processing takes 1 to 5 business
days, so this request goes in on day one even if nothing else does.

Enable the APIs the platform uses:

```bash
gcloud services enable \
  documentai.googleapis.com \
  aiplatform.googleapis.com \
  bigquery.googleapis.com \
  storage.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com
```

**Enabling an API and being able to use it are minutes apart.** Verified on the
first real run, 2026-09-03: `provision_data_plane.sh` enabled
`documentai.googleapis.com` and then failed to create the OCR processor in the
same pass, printing `DOCAI_PROCESSOR_ID=...<not-yet-created>` without an error.
Both scripts are idempotent, so the fix is to run each one twice. The second
pass reports every existing resource as already present and resolves the ids
the first pass could not.

## 2. Storage: two GCS buckets

```bash
gcloud storage buckets create gs://clearcut-scripts-intake --location=us-central1
gcloud storage buckets create gs://clearcut-legal-corpus --location=us-central1
```

`clearcut-scripts-intake` holds the uploaded screenplay PDFs. These are the
immutable originals; the pipeline reads from here and never writes back, so
every later stage can re-run against the exact bytes the producer uploaded.

`clearcut-legal-corpus` holds the legal reference documents that ground the
policy checks, organized with one prefix per jurisdiction:

```
gs://clearcut-legal-corpus/argentina/
gs://clearcut-legal-corpus/mexico/
gs://clearcut-legal-corpus/spain/
gs://clearcut-legal-corpus/usa/
...
```

The prefix is a filing convention for humans; the jurisdiction that matters at
query time comes from the metadata manifest in section 5.

## 3. Document AI processor

Create one Document OCR processor (the layout-aware kind) in the console under
Document AI > Processors, region `us`. It converts screenplay PDFs into text
with page and block structure, which the scene splitter downstream depends on.

The console shows the processor after creation. `DOCAI_PROCESSOR_ID` takes its
**full resource name**, `projects/clearcut-hack/locations/us/processors/<id>`,
not the bare id the console displays on its own: `DocumentAIIngestion` passes
the value straight into `ProcessRequest(name=...)`, which rejects anything
shorter. `infra/provision_data_plane.sh` prints the correct form. The ingestion
code reads it from the environment, never from a hardcoded string.

## 4. BigQuery dataset for lore vectors

One dataset holds the scene records and their embeddings:

```bash
bq mk --location=us-central1 clearcut
```

The application uses `BigQueryVectorStore` from `langchain-google-community`,
which creates its own table inside the dataset on first write. No schema work
is needed up front. Below 5,000 rows BigQuery brute-force scans the vectors
instead of using an index, and a hackathon corpus stays well under that line,
so skip index tuning entirely.

## 5. Vertex AI Search data store for legal grounding

**Discovery Engine rejects a bare user token.** Application Default
Credentials carry no quota project, and every call answers `403
PERMISSION_DENIED` with `reason: SERVICE_DISABLED` rather than saying so. The
message names the wrong cause: the API is enabled, the token is simply missing
a project. Send `x-goog-user-project: clearcut-hack` on every Discovery Engine
call; `infra/provision_retrieval_plane.sh` now does. Found on the first real
run, 2026-09-03, where its absence made the whole script a silent no-op that
still printed its success banner.

Create one Vertex AI Search data store (console: AI Applications > Data
Stores) over `gs://clearcut-legal-corpus`, type unstructured documents.
Vertex AI Search runs on the Discovery Engine API; enable
`discoveryengine.googleapis.com` if the console did not enable it during
creation.

Feed it a JSONL metadata manifest instead of pointing it at raw PDFs, because
the manifest is what carries the jurisdiction onto each document. Each line
describes one document:

```json
{"id": "arg-copyright-11723", "structData": {"jurisdiction": "argentina"}, "content": {"mimeType": "application/pdf", "uri": "gs://clearcut-legal-corpus/argentina/ley-11723.pdf"}}
```

**Warning, console-only step.** After import, the `jurisdiction` field must be
manually marked Indexable in the console under Data > Schema. There is no API
or gcloud flag for this at data store creation time, and nothing fails if you
skip it. Queries with a jurisdiction filter run without error and return
results from every jurisdiction, so a Mexico script quietly gets grounded
against US statutes. Mark the field Indexable before running any filtered
query, and verify with one query filtered to a jurisdiction that should return
zero results.

Create the Agent Builder agent app that hosts the project Q&A agent
(console: AI Applications > Agents) and attach this data store to it as a
grounding source; `infra/provision_retrieval_plane.sh` provisions it. The
running service never reads the resulting agent app id --
`VertexSearchGrounding` calls Vertex AI Search directly against the data
store id (`VERTEX_SEARCH_DATA_STORE_ID`, section 8). Per-request jurisdiction
filtering goes through the retrieval tool's `filter` field (for example
`jurisdiction: ANY("argentina")`), set by the agent from the production's
declared territory.

## 6. ClickHouse Cloud

Create one ClickHouse Cloud service (the free trial tier covers hackathon
load). It owns two tables:

- `tracker_items`: one row per finding per state change, with the textual
  state `BLOCKED`, `IN_PROGRESS`, or `CLEARED`, the scene reference, severity,
  and the rights-holder contact when Parallel has found one. The dashboard
  reads current state and history from this table.
- `script_versions`: one row per uploaded script version, so delta analysis
  between v1 and v2 can attribute each finding to the version that introduced
  it.

Connection credentials come from the service's console page and travel only
through environment variables (`CLICKHOUSE_HOST`, `CLICKHOUSE_USER`,
`CLICKHOUSE_PASSWORD`, section 8). The application connects with
`clickhouse-connect` over HTTPS on port 8443.

## 7. Parallel

Create an account at https://platform.parallel.ai and generate an API key; it
lands in the environment as `PARALLEL_API_KEY`. Every HTTP call carries it in
the `x-api-key` header. The Python SDK is `parallel-web` on PyPI, imported as
`from parallel import Parallel`, and it reads that same variable from the
environment. The API overview is at
https://docs.parallel.ai/getting-started/overview.

Three surfaces carry ClearCut's traffic.

**Task API** at `POST https://api.parallel.ai/v1/tasks/runs` runs the
rights-holder research that `docs/plan/sdd.md` section 3 assigns to the
`RightsResearch` port. A run takes an `input`, a `task_spec` naming the output
schema, and a `processor` tier. The result arrives with a `basis` object
holding per-field citations, the reasoning behind each field, and a confidence
value; those citations are what the tracker stores next to the finding, so a
producer can check the source before sending a legal request. See
https://docs.parallel.ai/task-api/task-quickstart and
https://docs.parallel.ai/task-api/guides/access-research-basis.

**Search API** at `POST https://api.parallel.ai/v1/search` takes an `objective`
in plain language plus two or three `search_queries`, and returns ranked
excerpts with URLs and publish dates. Its `mode` field sets the latency floor:
`turbo` near 250ms, `fast` near 700ms, `advanced` near 3s. See
https://docs.parallel.ai/search/search-quickstart.

**Search MCP** at `https://search.parallel.ai/mcp` wraps that same search for
tool calling and needs no auth header, though a bearer token raises the rate
limit. It is registered with the agent in Agent Builder as a tool endpoint,
which gives the agent live web search inside a clearance pass. A separate Task
MCP at `https://task-mcp.parallel.ai/mcp` exposes `createDeepResearch`,
`createTaskGroup`, `getStatus`, and `getResultMarkdown`, and stays available if
we later drive deep research from the agent instead of from our own adapter.
See https://docs.parallel.ai/integrations/mcp/quickstart.

Parallel keeps working examples for all of these in
https://github.com/parallel-web/parallel-cookbook, split into
`python-recipes/` and `typescript-recipes/`, with a `task-best-practices.md`
that covers task-spec design. The adapter in `adapters/parallel/research.py`
follows the Python recipes rather than inventing its own call shape.

### 7.1 Processor choice against the demo clock

Task API processors trade latency for depth:

| Processor | Median latency | Suits |
|---|---|---|
| `lite` | 45s | single-field lookup, fallback |
| `base` | 50s | roughly 5 fields of standard enrichment |
| `core` | 1.5min | roughly 10 cross-referenced fields |
| `core2x` | 3.5min | 10 fields at higher complexity |
| `pro` | 3.5min | roughly 20 fields, exploratory research |
| `ultra` through `ultra8x` | 4min to 8min | multi-source deep research, 25 fields |

ClearCut runs rights-holder research on `core`. "Who administers the sync
rights to Hotel California in Spain, and who do we write to" is a
cross-referenced question spanning ASCAP/BMI Songview, SADAIC, and label
sites, which is what `core` is sized for.

That tier does not fit inside the three-minute demo in `docs/plan/proposal.md`; a
`core` run at 1.5 minutes median eats half the recording. The demo therefore
splits the two call paths. The live lookup on camera goes through Search MCP
in `fast` mode, which answers inside a second. The Task API run for the same
finding starts at script upload, so its cited result is already stored by the
time we open the Hotel California finding. Both are real runtime traffic,
which is what the partner requirement asks for (section 11).

## 8. Secrets and configuration

Locally, a `.env` file at the repo root holds everything; it is gitignored and
never committed. In the deployed Cloud Run service, the same names come from
Secret Manager entries mounted as environment variables. The full set:

| Variable | Holds |
|---|---|
| `CLEARCUT_MODE` | `mock` for the in-memory demo, `live` for the real adapter graph; unset defaults to `live` |
| `GOOGLE_CLOUD_PROJECT` | project ID, `clearcut-hack` |
| `DOCAI_PROCESSOR_ID` | Document AI processor from section 3, as a full resource name: `projects/clearcut-hack/locations/us/processors/<id>` |
| `PARALLEL_API_KEY` | Parallel Task API, Search API, and MCP auth (`x-api-key`) |
| `CLICKHOUSE_HOST` | ClickHouse Cloud endpoint |
| `CLICKHOUSE_USER` | ClickHouse user |
| `CLICKHOUSE_PASSWORD` | ClickHouse password |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Grafana Cloud OTLP endpoint |
| `OTEL_EXPORTER_OTLP_HEADERS` | Grafana Cloud OTLP auth header |
| `GEMINI_MODEL` | `gemini-3.7-flash` |
| `GEMINI_MODEL_LITE` | `gemini-3.1-flash-lite` |
| `VERTEX_SEARCH_DATA_STORE_ID` | data store from section 5, as a full resource name: `projects/clearcut-hack/locations/global/collections/default_collection/dataStores/clearcut-legal-corpus` |
| `NOTIFY_WEBHOOK_URL` | outbound webhook the Notifier posts to |

The Notifier delivers every notification as an HTTP POST to
`NOTIFY_WEBHOOK_URL`; SMTP is deliberately out of scope for the demo, so the
webhook is the only outbound notification channel.

The Gemini model IDs are configuration, not code. Model swaps during the
hackathon (quota, pricing, a better release) then touch one env value instead
of a code search.

```bash
echo -n "$VALUE" | gcloud secrets create PARALLEL_API_KEY --data-file=-
# repeat per secret, then reference them in the deploy command below
```

## 9. Hosting: one Cloud Run service

One service hosts everything. The container build runs `npm run build` in
`web/`, copies the Vite output into the image, and the Flask process serves
those static files alongside the JSON API. One origin, so the browser never
makes a cross-origin request and no CORS configuration exists to break during
the demo. ADR 0010 records the decision to drop Replit and host everything on
this one Cloud Run service.

The command below carries all ten `_required_env` variables (section 8).
`DOCAI_PROCESSOR_ID`, `CLICKHOUSE_HOST`, `CLICKHOUSE_USER`, and
`NOTIFY_WEBHOOK_URL` have no fixed value, so export them in the deploying
shell first; the rest are the literal values fixed elsewhere in this
document.

```bash
gcloud run deploy clearcut \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances 0 \
  --set-secrets "PARALLEL_API_KEY=PARALLEL_API_KEY:latest,CLICKHOUSE_PASSWORD=CLICKHOUSE_PASSWORD:latest" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=clearcut-hack,GEMINI_MODEL=gemini-3.7-flash,GEMINI_MODEL_LITE=gemini-3.1-flash-lite,DOCAI_PROCESSOR_ID=$DOCAI_PROCESSOR_ID,CLICKHOUSE_HOST=$CLICKHOUSE_HOST,CLICKHOUSE_USER=$CLICKHOUSE_USER,VERTEX_SEARCH_DATA_STORE_ID=$VERTEX_SEARCH_DATA_STORE_ID,NOTIFY_WEBHOOK_URL=$NOTIFY_WEBHOOK_URL"
```

Min instances stays at 0. This is a demo; a cold start of a few seconds costs
nothing, while an always-warm instance burns the $100 credit for no judged
benefit.
The service account needs `roles/documentai.apiUser`, `roles/aiplatform.user`,
`roles/bigquery.dataEditor`, and `roles/storage.objectAdmin` on the two
buckets.

## 10. Grafana Cloud (required)

Our architecture requires Grafana Cloud plus OpenTelemetry per ADR 0008; the
hackathon does not. Create a free Grafana Cloud stack, then under Connections > OpenTelemetry
copy the OTLP endpoint and generate a token. These become
`OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS`
(`Authorization=Basic <base64 instance:token>`).

The Flask app initializes the OpenTelemetry SDK at startup and exports traces
and metrics over OTLP. The dashboard JSON is `infra/grafana_dashboard.json`.
Four panels query the metric names the adapters emit:

- Stage latency: `clearcut_stage_latency_ms` (ingest, extract, ground, research, track)
- Tokens per model: `clearcut_gemini_tokens_total`
- Findings by severity: `clearcut_findings_total`
- Tracker items by state: `clearcut_tracker_items` (`BLOCKED` / `IN_PROGRESS` / `CLEARED`)

Publish it with `infra/provision_grafana_dashboard.py`. `--dry-run` prints the
panels and connects to nothing. A real run needs `GRAFANA_URL` (the stack URL,
`https://<slug>.grafana.net`) and `GRAFANA_TOKEN` (a Grafana service account
token with dashboards:write). The OTLP variables authenticate the exporter;
they do not authenticate the Grafana HTTP API.

Screenshot this dashboard for the demo video; it is the fastest way to show
judges a live multi-stage pipeline rather than a single prompt call.

## 11. Submission checklist

| Item | Requirement |
|---|---|
| Hosted URL | the Cloud Run service URL, publicly reachable |
| Repository | public, with the Apache-2.0 `LICENSE` at root (already present) |
| Demo video | 3 minutes, English or subtitled |
| Devpost form | submitted before September 7, 2026 |
| Runtime proof | the repo shows real runtime calls to Google Cloud (Gemini, Document AI) and Parallel (Task API, MCP), not mocked responses |

The runtime-proof row is the one judges verify against the code, so keep the
Parallel and Gemini call sites obvious in the repository rather than buried
behind abstraction layers.
