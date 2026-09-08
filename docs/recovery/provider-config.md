# Provider models and operation budgets

`ProviderConfig` is the shared validated configuration for model identifiers and
supported provider operation budgets. The required `GEMINI_MODEL` and
`GEMINI_MODEL_LITE` environment variables remain compatible. Optional
`CLEARCUT_PROVIDER_OPTIONS` accepts a JSON object containing only these fields:

| Field | Default |
| --- | --- |
| `grounding_model` | `gemini-3.1-flash-lite` |
| `embedding_model` | `text-embedding-005` |
| `speech_model` | `chirp_2` |
| `research_processor` | `core` |
| `genai_timeout` | 120 seconds |
| `document_timeout` | 120 seconds |
| `bigquery_timeout` | 30 seconds |
| `search_timeout` | 45 seconds |
| `research_create_timeout` | 30 seconds |
| `research_result_timeout` | 300 seconds |
| `speech_timeout` | 45 seconds |
| `clickhouse_connect_timeout` | 10 seconds |
| `clickhouse_request_timeout` | 30 seconds |

The extraction and continuity model fields can also be explicitly overridden.
Timeouts must be finite numbers between 0.001 and 3600 seconds. Unknown fields,
credentials and malformed options fail configuration. All options, without
credentials, are frozen into newly queued analysis requests; later environment
changes do not silently change an existing job's selected models or budgets.

GenAI uses milliseconds internally: the composition root converts seconds once
and sets one attempt, including the original request. Extraction and grounding
use the global endpoint; embeddings keep the dataset's `us-central1` region.
The installed embeddings helper replaces a constructor-supplied client during
validation, so composition explicitly assigns its public `client` field after
validation. A test checks the resulting real SDK client's region and timeout.
Its outer retry wrapper is also limited to one attempt.

Document AI and Speech pass `retry=None` with explicit timeouts. Parallel Search
and Task use `max_retries=0`; Task creation never automatically replays an unknown
accepted request. ClickHouse queries use zero SDK retries; the durable outbox
owns retry scheduling and deduplication. These choices prevent hidden retry
multiplication with the durable worker's bounded attempts.

This checkpoint does **not** claim every integration is fully bounded. The
native BigQuery adapter now bounds query/load/poll operations; its new scene
projection SQL and deployment still require live verification (see lore-projection.md). Webhook delivery needs the scoped destination
and outbox implementation described in the recovery checklist. Firestore/GCS
operation policies and full live provider failure verification remain release
checks. The configuration does not grant access to a model or certify that a
new model/region choice supports all required languages and operations.

Installed SDK contracts were checked locally: GenAI 2.20.0 documents timeout in
milliseconds and retry attempts including the initial request; Parallel 1.3.2
accepts operation-specific timeouts; VertexAIEmbeddings 3.2.4 exposes the public
client field but replaces constructor input in `validate_environment`.
