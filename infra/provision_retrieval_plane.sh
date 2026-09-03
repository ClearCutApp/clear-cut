#!/usr/bin/env bash
#
# provision_retrieval_plane.sh -- idempotent provisioning for ClearCut's
# retrieval plane: the Discovery Engine API, the Vertex AI Search data store
# over gs://clearcut-legal-corpus, the JSONL metadata manifest import, and
# the Agent Builder agent app that grounds project Q&A against it
# (docs/plan/infrastructure.md section 5).
#
# Usage:
#   MANIFEST_FILE=path/to/manifest.jsonl infra/provision_retrieval_plane.sh [--dry-run]
#
# --dry-run prints every command this script would run, including the guard
# that checks whether a resource already exists, and executes none of them.
# Without it, the script requires gcloud on PATH, runs the real commands,
# and skips any resource a guard finds already present.
#
# MANIFEST_FILE (default infra/legal_corpus_manifest.jsonl) must already
# exist and be non-empty: infra/build_manifest.py builds it from a bucket
# listing, this script only imports it. See infra/README.md for the full
# pipeline.
#
# Vertex AI Search data stores, document import, and Engine apps have no
# gcloud command group, so every call here goes through the REST API with
# curl and a gcloud-issued access token -- the same pattern
# provision_data_plane.sh uses for the Document AI processor.
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-clearcut-hack}"
LOCATION="global"
CORPUS_BUCKET="gs://clearcut-legal-corpus"
DATA_STORE_ID="clearcut-legal-corpus"
DATA_STORE_DISPLAY_NAME="ClearCut Legal Corpus"
ENGINE_ID="clearcut-project-qa"
ENGINE_DISPLAY_NAME="ClearCut Project Q&A"
MANIFEST_FILE="${MANIFEST_FILE:-infra/legal_corpus_manifest.jsonl}"
MANIFEST_GCS_URI="$CORPUS_BUCKET/_manifest/legal_corpus_manifest.jsonl"
AGENT_BUILDER_AGENT_ID=""
DRY_RUN=0

usage() {
  cat <<'USAGE'
Usage: provision_retrieval_plane.sh [--dry-run]

  --dry-run   Print every command this script would run, and execute none.

MANIFEST_FILE (default infra/legal_corpus_manifest.jsonl) selects the JSONL
manifest infra/build_manifest.py produced; see infra/README.md for the full
command that builds it.
USAGE
}

die() {
  echo "provision_retrieval_plane.sh: $1" >&2
  exit 1
}

parse_args() {
  local arg
  for arg in "$@"; do
    case "$arg" in
      --dry-run) DRY_RUN=1 ;;
      *)
        usage >&2
        exit 1
        ;;
    esac
  done
}

require_gcloud() {
  command -v gcloud >/dev/null 2>&1 || die "gcloud is required but was not found on PATH"
}

require_manifest() {
  [ -s "$MANIFEST_FILE" ] \
    || die "manifest file $MANIFEST_FILE is missing or empty -- run infra/build_manifest.py first"
}

# print_cmd CMD... prints a copy-pasteable, shell-quoted form of CMD.
print_cmd() {
  printf '%s\n' "$(printf '%q ' "$@")"
}

# run CMD... prints CMD, then executes it unless --dry-run is set.
run() {
  print_cmd "$@"
  [ "$DRY_RUN" -eq 1 ] && return 0
  "$@"
}

enable_apis() {
  run gcloud services enable discoveryengine.googleapis.com
}

discovery_engine_url() {
  printf 'https://discoveryengine.googleapis.com/v1/projects/%s/locations/%s/collections/default_collection/%s' \
    "$PROJECT_ID" "$LOCATION" "$1"
}

# print_curl_get_cmd URL prints URL as a bearer-token GET, trace only.
# Kept separate from fetch_json below so a caller capturing the response
# body with command substitution never captures this trace line too.
print_curl_get_cmd() {
  local auth
  # shellcheck disable=SC2016 # printed literally; the real call substitutes
  # a fresh token instead of the one captured when this string was built.
  auth='Authorization: Bearer $(gcloud auth print-access-token)'
  print_cmd curl -sS -H "$auth" "$1"
}

# fetch_json URL issues the real bearer-token GET and returns the body.
# Callers guard this behind `[ "$DRY_RUN" -eq 0 ]` themselves.
fetch_json() {
  curl -sS -H "Authorization: Bearer $(gcloud auth print-access-token)" "$1"
}

# print_curl_post_cmd URL PAYLOAD prints URL and PAYLOAD as a bearer-token
# POST, trace only. Kept separate from post_json below so a caller
# capturing the response body with command substitution never captures
# this trace line too.
print_curl_post_cmd() {
  local auth
  # shellcheck disable=SC2016 # printed literally; the real call substitutes
  # a fresh token instead of the one captured when this string was built.
  auth='Authorization: Bearer $(gcloud auth print-access-token)'
  print_cmd curl -sS -X POST -H "$auth" -H 'Content-Type: application/json' -d "$2" "$1"
}

# post_json URL PAYLOAD issues the real bearer-token POST and returns the
# body. Callers guard this behind `[ "$DRY_RUN" -eq 0 ]` themselves.
post_json() {
  curl -sS -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    -H 'Content-Type: application/json' -d "$2" "$1"
}

# curl_auth_post URL PAYLOAD prints URL and PAYLOAD as a bearer-token POST,
# then issues it for real unless --dry-run is set. The response body is
# discarded -- a caller that needs it calls post_json directly instead.
curl_auth_post() {
  print_curl_post_cmd "$1" "$2"
  [ "$DRY_RUN" -eq 1 ] && return 0
  post_json "$1" "$2" >/dev/null
}

create_data_store() {
  echo "  data store $DATA_STORE_ID over $CORPUS_BUCKET (unstructured documents)"
  local get_url create_url body=""
  get_url="$(discovery_engine_url "dataStores/$DATA_STORE_ID")"
  create_url="$(discovery_engine_url "dataStores?dataStoreId=$DATA_STORE_ID")"
  print_curl_get_cmd "$get_url"
  if [ "$DRY_RUN" -eq 0 ]; then
    body="$(fetch_json "$get_url")"
  fi
  if [ "$DRY_RUN" -eq 0 ] && printf '%s' "$body" | grep -q "\"name\": *\"projects/"; then
    echo "  data store $DATA_STORE_ID already exists, skipping create"
    return 0
  fi
  local payload
  payload="{\"displayName\":\"$DATA_STORE_DISPLAY_NAME\",\"industryVertical\":\"GENERIC\","
  payload+="\"solutionTypes\":[\"SOLUTION_TYPE_SEARCH\"],\"contentConfig\":\"CONTENT_REQUIRED\"}"
  curl_auth_post "$create_url" "$payload"
}

# upload_manifest copies the local manifest infra/build_manifest.py wrote to
# a GCS path the import API can read from -- Discovery Engine's gcsSource
# takes a gs:// URI, never a local path.
upload_manifest() {
  run gcloud storage cp "$MANIFEST_FILE" "$MANIFEST_GCS_URI"
}

import_documents() {
  local url payload
  url="$(discovery_engine_url "dataStores/$DATA_STORE_ID/branches/0/documents:import")"
  payload="{\"gcsSource\":{\"inputUris\":[\"$MANIFEST_GCS_URI\"],\"dataSchema\":\"document\"},"
  payload+="\"reconciliationMode\":\"INCREMENTAL\"}"
  curl_auth_post "$url" "$payload"
}

# agent_id_from BODY extracts the trailing id off an engine's "name" field
# ("projects/P/locations/L/collections/C/engines/ID") in a JSON response.
agent_id_from() {
  printf '%s' "$1" | sed -n \
    's#.*"name": *"projects/[^"]*/locations/[^"]*/collections/[^"]*/engines/\([^"]*\)".*#\1#p' \
    | head -1
}

create_engine() {
  local get_url create_url body=""
  get_url="$(discovery_engine_url "engines/$ENGINE_ID")"
  create_url="$(discovery_engine_url "engines?engineId=$ENGINE_ID")"
  print_curl_get_cmd "$get_url"
  if [ "$DRY_RUN" -eq 0 ]; then
    body="$(fetch_json "$get_url")"
  fi
  if [ "$DRY_RUN" -eq 0 ] && printf '%s' "$body" | grep -q "\"name\": *\"projects/"; then
    echo "  agent app $ENGINE_ID already exists, skipping create"
    AGENT_BUILDER_AGENT_ID="$(agent_id_from "$body")"
    return 0
  fi
  create_engine_call "$create_url"
}

create_engine_call() {
  local url="$1" payload resp
  payload="{\"displayName\":\"$ENGINE_DISPLAY_NAME\",\"dataStoreIds\":[\"$DATA_STORE_ID\"],"
  payload+="\"solutionType\":\"SOLUTION_TYPE_SEARCH\"}"
  print_curl_post_cmd "$url" "$payload"
  if [ "$DRY_RUN" -eq 0 ]; then
    resp="$(post_json "$url" "$payload")"
    AGENT_BUILDER_AGENT_ID="$(agent_id_from "$resp")"
  fi
}

# data_store_path is the form VERTEX_SEARCH_DATA_STORE_ID must carry.
#
# `VertexSearchGrounding` passes the value straight into
# `types.VertexAISearch(datastore=...)` (adapters/gcp/vertex_search.py:92),
# which needs a complete resource name. LOCATION is "global" because that is
# where create_data_store puts it -- an earlier unit test asserted
# "locations/us" against a fake, and a fake accepts either.
data_store_path() {
  printf 'projects/%s/locations/%s/collections/default_collection/dataStores/%s' \
    "$PROJECT_ID" "$LOCATION" "$DATA_STORE_ID"
}

print_env_line() {
  cat <<EOF

# .env line this run resolved -- paste into the repo-root .env file:
VERTEX_SEARCH_DATA_STORE_ID=$(data_store_path)
EOF
}

# print_indexable_warning is the last thing main() calls, on every run
# including --dry-run: marking "jurisdiction" Indexable has no API and no
# gcloud flag, and skipping it fails silently rather than loudly (see
# infra/README.md and docs/plan/infrastructure.md section 5).
print_indexable_warning() {
  cat <<'EOF'

======================================================================
MANUAL STEP REQUIRED -- mark "jurisdiction" Indexable in the console
Console path: AI Applications > Data Stores > clearcut-legal-corpus >
Data > Schema > jurisdiction > toggle Indexable on > Save.
There is no API call and no gcloud flag for this step, and nothing fails
if you skip it: a jurisdiction-filtered query still runs without error,
but it silently returns documents from every jurisdiction instead of the
one requested -- a Mexico script would be quietly grounded against US
statutes. Verify by running one query filtered to a jurisdiction that
should return zero results before trusting any grounded answer.
======================================================================
EOF
}

main() {
  parse_args "$@"
  require_gcloud
  require_manifest
  echo "Provisioning ClearCut retrieval plane (project: $PROJECT_ID, dry-run: $DRY_RUN)"
  enable_apis
  create_data_store
  upload_manifest
  import_documents
  create_engine
  print_env_line
  print_indexable_warning
}

main "$@"
