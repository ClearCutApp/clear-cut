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

The console shows the processor ID after creation. Copy it into configuration
as `DOCAI_PROCESSOR_ID` (section 8); the ingestion code reads it from the
environment, never from a hardcoded string.

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
grounding source. Copy the agent app ID into configuration as
`AGENT_BUILDER_AGENT_ID` (section 8). Per-request jurisdiction filtering goes
through the retrieval tool's `filter` field (for example `jurisdiction:
ANY("argentina")`), set by the agent from the production's declared
territory.

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

Create an account at parallel.ai and generate an API key; it lands in the
environment as `PARALLEL_API_KEY`.

Two integration points use it. The Task API handles rights-holder research:
given a detected trademark, song, or likeness, a task run returns the current
holder and a legal or licensing contact. The MCP server at
`https://search.parallel.ai/mcp` is registered with the agent in Agent
Builder as a tool endpoint, which gives the agent live web search during a
clearance pass. Both must appear in runtime traffic during the demo, since
partner runtime usage is a judged requirement (section 11).

## 8. Secrets and configuration

Locally, a `.env` file at the repo root holds everything; it is gitignored and
never committed. In the deployed Cloud Run service, the same names come from
Secret Manager entries mounted as environment variables. The full set:

| Variable | Holds |
|---|---|
| `GOOGLE_CLOUD_PROJECT` | project ID, `clearcut-hack` |
| `DOCAI_PROCESSOR_ID` | Document AI processor from section 3 |
| `PARALLEL_API_KEY` | Parallel Task API and MCP auth |
| `CLICKHOUSE_HOST` | ClickHouse Cloud endpoint |
| `CLICKHOUSE_USER` | ClickHouse user |
| `CLICKHOUSE_PASSWORD` | ClickHouse password |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Grafana Cloud OTLP endpoint |
| `OTEL_EXPORTER_OTLP_HEADERS` | Grafana Cloud OTLP auth header |
| `GEMINI_MODEL` | `gemini-3.7-flash` |
| `GEMINI_MODEL_LITE` | `gemini-3.1-flash-lite` |
| `AGENT_BUILDER_AGENT_ID` | Agent Builder agent app for project Q&A, section 5 |
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

```bash
gcloud run deploy clearcut \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances 0 \
  --set-secrets "PARALLEL_API_KEY=PARALLEL_API_KEY:latest,CLICKHOUSE_PASSWORD=CLICKHOUSE_PASSWORD:latest" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=clearcut-hack,GEMINI_MODEL=gemini-3.7-flash,GEMINI_MODEL_LITE=gemini-3.1-flash-lite"
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
and metrics over OTLP. Build one dashboard with the pipeline metrics:

- per-stage latency (ingest, extract, ground, research, track)
- tokens per Gemini call, split by model
- findings by severity
- tracker items by state (`BLOCKED` / `IN_PROGRESS` / `CLEARED`)

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
