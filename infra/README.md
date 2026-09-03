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
2. `infra/provision_data_plane.sh` — run it for real, then **run it a second
   time**. Enabling an API and being able to call it are minutes apart: on the
   first real run, 2026-09-03, the Document AI processor failed to create in
   the same pass that enabled its API, and the script printed
   `DOCAI_PROCESSOR_ID=...<not-yet-created>` without an error. The second pass
   skips every resource that already exists and resolves the ids the first
   could not.
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
8. `.venv/bin/python infra/provision_tracker_schema.py --dry-run` — review the
   two `CREATE TABLE IF NOT EXISTS` statements, then drop `--dry-run` to create
   `tracker_items` and `script_versions` in ClickHouse Cloud. It reads
   `CLICKHOUSE_HOST`, `CLICKHOUSE_USER` and `CLICKHOUSE_PASSWORD` from the
   environment and exits naming any that are missing.

   It needs the project interpreter, not a bare `python3`: it reuses
   `ClickHouseTrackerStore.ensure_schema()` so the schema has one definition
   rather than two, which means it imports the adapter and its dependencies.

   ClickHouse Cloud itself is still created by hand — this script provisions
   the tables inside a service that already exists.

9. `.venv/bin/python infra/seed_project_bible.py --dry-run` — review the fact
   it would index, then drop `--dry-run` to write it into the BigQuery lore
   table. It reads `GOOGLE_CLOUD_PROJECT` and exits naming it if absent.

   The fact comes from `adapters/demo/scenario.py`, so what this seeds and what
   mock mode serves cannot disagree about which fact scene 3 contradicts. It is
   additive: running it twice indexes the fact twice, because `LoreStore` has
   no way to remove a row (SDD section 4.3).

10. `.venv/bin/python infra/fetch_legal_corpus.py AR --dry-run` — review the
    searches, then drop `--dry-run` to ask Parallel for each category's statute.
    It needs `PARALLEL_API_KEY` and prints candidate URLs rather than uploading
    them: it rejects anything not on a government or intergovernmental domain,
    and a human still confirms a document is the right law before it becomes
    something ClearCut cites to a producer.

    Corpus coverage is the limit on legal grounding, not query phrasing. Six of
    the eight clearance categories currently ground against nothing for
    Argentina, because no statute covering them has been loaded.

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
