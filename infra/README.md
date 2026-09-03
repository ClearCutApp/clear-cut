# Infrastructure

Scripts that provision the Google Cloud resources `docs/plan/infrastructure.md`
otherwise asks you to create by hand. Each is idempotent and supports
`--dry-run`, which prints every command it would run and executes none of
them.

## Prerequisites

Create the Google Cloud project and request the hackathon credits first
(`docs/plan/infrastructure.md` §1); these scripts provision resources inside an
existing project, not the project itself. Have the `gcloud` CLI installed,
authenticated (`gcloud auth login`), and pointed at that project
(`gcloud config set project clearcut-hack`) before running anything below.

## Run order

1. `infra/provision_data_plane.sh --dry-run` — review the commands it would
   run: the seven APIs, the two GCS buckets, the `clearcut` BigQuery dataset,
   the Document AI OCR processor, and the Secret Manager containers of
   `docs/plan/infrastructure.md` §8.
2. `infra/provision_data_plane.sh` — run it for real. It skips any resource
   that already exists, so re-running it after a partial failure is safe.
3. Copy the printed lines into a `.env` file at the repo root. `.env` is the
   destination for everything these scripts print, both the resolved values
   (`GOOGLE_CLOUD_PROJECT`, `DOCAI_PROCESSOR_ID`, the two Gemini model ids)
   and the reminder commands for the secrets it created empty.
4. `gcloud storage ls "gs://clearcut-legal-corpus/**" | infra/build_manifest.py
   > infra/legal_corpus_manifest.jsonl` — list the corpus bucket and map each
   object into the JSONL metadata manifest `docs/plan/infrastructure.md` §5
   describes, one line per document with its `structData.jurisdiction`.
5. `infra/provision_retrieval_plane.sh --dry-run` — review the commands it
   would run: enabling the Discovery Engine API, creating the Vertex AI
   Search data store over `gs://clearcut-legal-corpus`, importing the
   manifest, and registering the Agent Builder agent app against that data
   store.
6. `infra/provision_retrieval_plane.sh` — run it for real. It prints a
   warning as the last thing it does, on every run; read the section below
   before trusting any grounded answer this system produces.
7. Copy `VERTEX_SEARCH_DATA_STORE_ID` from the script's output into `.env`.
   It is the **full resource name**, not the bare id, because
   `types.VertexAISearch(datastore=...)` rejects anything shorter.

   Do not add `AGENT_BUILDER_AGENT_ID`. The script reports the agent app id,
   but nothing under `src/` reads it (section 5 says so explicitly), and
   `tests/unit/test_environment_contract.py` fails if the name appears in
   `.env.example`.

## The manual step inside Google Cloud

Step 6 above cannot finish the retrieval plane by itself. One step has no
API and no `gcloud` flag, and the script cannot perform it:

1. [ ] Mark the `jurisdiction` field Indexable. Console: AI Applications >
   Data Stores > `clearcut-legal-corpus` > Data > Schema >
   `jurisdiction` > toggle Indexable on > Save.

Skip this and nothing errors. A jurisdiction-filtered query still runs and
still returns an answer, grounded in documents from every jurisdiction
instead of the one requested, so a Mexico script gets grounded against US
statutes without any signal that something is wrong. Verify the field is
Indexable by running one query filtered to a jurisdiction that should return
zero results, and confirm it does, before trusting any grounded answer.

## Manual steps outside Google Cloud

ClickHouse Cloud (`docs/plan/infrastructure.md` §6) and Grafana Cloud (§10) are
external SaaS signups. No script here automates either: create both
accounts by hand, then paste their connection details into `.env` yourself —
`CLICKHOUSE_HOST`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`,
`OTEL_EXPORTER_OTLP_ENDPOINT`, and `OTEL_EXPORTER_OTLP_HEADERS`.
