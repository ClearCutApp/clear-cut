#!/usr/bin/env bash
#
# provision_data_plane.sh -- idempotent provisioning for ClearCut's Google
# Cloud data plane: the seven APIs, the two GCS buckets, the BigQuery
# dataset, the Document AI OCR processor, and the Secret Manager containers
# of docs/plan/infrastructure.md sections 1-4 and 8.
#
# Usage:
#   infra/provision_data_plane.sh [--dry-run]
#
# --dry-run prints every command this script would run, including the guard
# that checks whether a resource already exists, and executes none of them.
# Without it, the script requires gcloud on PATH, runs the real commands,
# and skips any resource a guard finds already present.
#
# Document AI has no gcloud command group, so its guard and create calls go
# through the REST API with curl and a gcloud-issued access token instead of
# a gcloud subcommand; every other resource here uses gcloud or bq directly.
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-clearcut-hack}"
REGION="us-central1"
DOCAI_LOCATION="us"
SCRIPTS_BUCKET="gs://clearcut-scripts-intake"
CORPUS_BUCKET="gs://clearcut-legal-corpus"
DATASET="clearcut"
PROCESSOR_DISPLAY_NAME="clearcut-ocr"
DOCAI_PROCESSOR_ID=""
DRY_RUN=0

APIS=(
  documentai.googleapis.com
  aiplatform.googleapis.com
  bigquery.googleapis.com
  storage.googleapis.com
  run.googleapis.com
  secretmanager.googleapis.com
  artifactregistry.googleapis.com
)

# Secret Manager holds the values this script cannot know at provisioning
# time: external credentials for Parallel, ClickHouse Cloud, and Grafana
# Cloud. GOOGLE_CLOUD_PROJECT, DOCAI_PROCESSOR_ID, and the Gemini model ids
# are plain configuration (docs/plan/infrastructure.md section 8), not secrets,
# so they are printed as .env lines instead of created here.
SECRETS=(
  PARALLEL_API_KEY
  CLICKHOUSE_HOST
  CLICKHOUSE_USER
  CLICKHOUSE_PASSWORD
  OTEL_EXPORTER_OTLP_ENDPOINT
  OTEL_EXPORTER_OTLP_HEADERS
  NOTIFY_WEBHOOK_URL
)

usage() {
  cat <<'USAGE'
Usage: provision_data_plane.sh [--dry-run]

  --dry-run   Print every command this script would run, and execute none.
USAGE
}

die() {
  echo "provision_data_plane.sh: $1" >&2
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

# guard_exists CMD... prints CMD as the existence check for the resource it
# describes. In --dry-run mode it always reports "not found" so the create
# command that follows prints too, next to its guard. In a real run, CMD's
# exit status decides: 0 means the resource already exists.
guard_exists() {
  print_cmd "$@"
  [ "$DRY_RUN" -eq 1 ] && return 1
  "$@" >/dev/null 2>&1
}

enable_apis() {
  run gcloud services enable "${APIS[@]}"
}

create_bucket() {
  local bucket="$1"
  if guard_exists gcloud storage buckets describe "$bucket"; then
    echo "  $bucket already exists, skipping create"
    return 0
  fi
  run gcloud storage buckets create "$bucket" --location="$REGION"
}

create_bigquery_dataset() {
  if guard_exists bq show --dataset "$DATASET"; then
    echo "  BigQuery dataset $DATASET already exists, skipping create"
    return 0
  fi
  run bq mk --location="$REGION" "$DATASET"
}

docai_processors_url() {
  printf 'https://%s-documentai.googleapis.com/v1/projects/%s/locations/%s/processors' \
    "$DOCAI_LOCATION" "$PROJECT_ID" "$DOCAI_LOCATION"
}

# docai_processor_id_from BODY extracts a processor's full "name" field
# ("projects/P/locations/L/processors/ID") from a JSON response.
#
# The full path, not the trailing id. `DocumentAIIngestion` passes this value
# straight into `ProcessRequest(name=...)` (adapters/gcp/document_ai.py:149),
# which the API rejects unless it is a complete resource name. An earlier
# version of this function stripped the path down to the bare id, which meant
# provisioning as documented produced a .env that failed on the first
# ingestion call -- and no test could see it, because the only consumer under
# test was a fake that accepts any string.
docai_processor_id_from() {
  printf '%s' "$1" | sed -n \
    's#.*"name": *"\(projects/[^"]*/locations/[^"]*/processors/[^"]*\)".*#\1#p' \
    | head -1
}

create_docai_processor() {
  local url auth body
  url="$(docai_processors_url)"
  # shellcheck disable=SC2016 # printed literally; the real call substitutes
  # a fresh token instead of the one captured when this string was built.
  auth='Authorization: Bearer $(gcloud auth print-access-token)'
  print_cmd curl -sS -H "$auth" "$url"
  body=""
  if [ "$DRY_RUN" -eq 0 ]; then
    body="$(curl -sS -H "Authorization: Bearer $(gcloud auth print-access-token)" "$url")"
  fi
  if [ "$DRY_RUN" -eq 0 ] && printf '%s' "$body" | grep -q "\"displayName\": *\"$PROCESSOR_DISPLAY_NAME\""; then
    echo "  Document AI processor $PROCESSOR_DISPLAY_NAME already exists, skipping create"
    DOCAI_PROCESSOR_ID="$(docai_processor_id_from "$body")"
    return 0
  fi
  create_docai_processor_call "$url" "$auth"
}

create_docai_processor_call() {
  local url="$1" auth="$2" payload resp
  payload="{\"type\":\"OCR_PROCESSOR\",\"displayName\":\"$PROCESSOR_DISPLAY_NAME\"}"
  print_cmd curl -sS -X POST -H "$auth" -H 'Content-Type: application/json' -d "$payload" "$url"
  [ "$DRY_RUN" -eq 1 ] && return 0
  resp="$(curl -sS -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    -H 'Content-Type: application/json' -d "$payload" "$url")"
  DOCAI_PROCESSOR_ID="$(docai_processor_id_from "$resp")"
}

create_secrets() {
  print_cmd gcloud secrets list --format='value(name)'
  local existing=""
  if [ "$DRY_RUN" -eq 0 ]; then
    existing="$(gcloud secrets list --format='value(name)')"
  fi
  local name
  for name in "${SECRETS[@]}"; do
    if [ "$DRY_RUN" -eq 0 ] && printf '%s\n' "$existing" | grep -qx "$name"; then
      echo "  secret $name already exists, skipping create"
      continue
    fi
    run gcloud secrets create "$name" --replication-policy=automatic
  done
}

print_env_lines() {
  cat <<EOF

# .env lines this run resolved -- paste into the repo-root .env file:
GOOGLE_CLOUD_PROJECT=$PROJECT_ID
DOCAI_PROCESSOR_ID=${DOCAI_PROCESSOR_ID:-projects/$PROJECT_ID/locations/$DOCAI_LOCATION/processors/<not-yet-created>}
GEMINI_MODEL=gemini-3.7-flash
GEMINI_MODEL_LITE=gemini-3.1-flash-lite

# Secret Manager containers created empty above; populate each once the
# value exists, for example:
#   echo -n "\$VALUE" | gcloud secrets versions add PARALLEL_API_KEY --data-file=-
EOF
}

main() {
  parse_args "$@"
  require_gcloud
  echo "Provisioning ClearCut data plane (project: $PROJECT_ID, dry-run: $DRY_RUN)"
  enable_apis
  create_bucket "$SCRIPTS_BUCKET"
  create_bucket "$CORPUS_BUCKET"
  create_bigquery_dataset
  create_docai_processor
  create_secrets
  print_env_lines
}

main "$@"
