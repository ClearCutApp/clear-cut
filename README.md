# clear-cut

Current production recovery scope and evidence: [specification](docs/recovery/specification.md),
[situation](docs/recovery/situation-2026-09-06.md), and [remaining work](docs/recovery/checklist.md).
The public entry is `/`; the workspace is `/projects`. Live account access requires
[Firebase/Firestore provisioning](docs/recovery/provisioning.md). Production readiness
remains unverified; historical MVP completion claims do not establish release status.

The Ultimate Agentic Cinema Clearance Engine

## Run locally

Prerequisites: Python 3.11+, and Node 20.19+ if you want the browser dashboard
instead of curl output.

Install everything with one command:

```bash
./.claude/init.sh
```

Start the mock demo, which needs no `.env` file:

```bash
CLEARCUT_MODE=mock ./.venv/bin/python main.py
```

In another terminal, upload the planted script, then read back the tracker it
populates. Run the upload first -- the tracker holds nothing until an analysis
writes to it, and a fresh read here returns `[]`.

```bash
curl -X POST http://127.0.0.1:8080/api/projects/demo-project/scripts \
  -H "Content-Type: application/json" \
  -d '{"gcs_uri":"gs://clearcut-demo/planted-script-v1.pdf","jurisdiction_code":"AR","version":1}'

curl http://127.0.0.1:8080/api/projects/demo-project/tracker-items
```

Both paths name the project they act on. The project id is a path segment, not
a query parameter and not a body field, because every resource in this API
hangs off the project that owns it.

The first call returns three findings -- an industrial-property mark, a music
sync, and a continuity contradiction -- on pages 3, 5 and 8. The second returns
a JSON array of three `BLOCKED` tracker items. Two carry a rights holder's
contact address; the continuity item names no rights holder, so its contact is
an empty string.

The API documents itself. With the server running, `GET /api/openapi.json`
serves the OpenAPI document and `http://127.0.0.1:8080/api/docs` serves a
Swagger UI over it.

To see the dashboard instead of raw JSON, build the SPA once and reload the
same address:

```bash
cd web && npm install && npm run build
```

## Live mode

Live mode connects to real Google Cloud, ClickHouse and Parallel services. Copy
`.env.example` to `.env`, fill in every value, and run:

```bash
CLEARCUT_MODE=live ./.venv/bin/python main.py
```

A blank `OTEL_EXPORTER_OTLP_ENDPOINT=` line in that copy counts as set, not
empty, and starts an exporter that retries against nothing. The mock demo above
never touches this file, so skip it there.

`CLEARCUT_MODE` defaults to `live`. A deployment that forgets to set it fails
loudly on a missing credential rather than quietly serving planted data.

## Gates

```bash
./.claude/init.sh check   # the seven gates: ruff, ruff format, mypy, pytest,
                          # stylelint, tsc, vitest
./.claude/init.sh live    # the live tier, which needs .env
```

The live tier reports how many tests actually ran. A run where every test
skipped is named as a configuration gap, not reported as a pass -- an
all-skipped run reached no service, and the tier exists to catch exactly that.
