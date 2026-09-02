# clear-cut
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

In another terminal, upload the planted script, then read back the tracker
it populates. Run analyze first -- the tracker holds nothing until an
analyze call writes to it, and a fresh `GET /api/tracker` here returns `[]`.

```bash
curl -X POST http://127.0.0.1:8080/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"project_id":"demo-project","gcs_uri":"gs://clearcut-demo/planted-script-v1.pdf","jurisdiction_code":"AR","version":1}'

curl "http://127.0.0.1:8080/api/tracker?project_id=demo-project"
```

The first call returns three findings (a trademark, a music sync, and a
continuity contradiction); the second returns three BLOCKED tracker items.
Two carry a rights holder's contact email; the continuity item names no
rights holder, so its contact is an empty string.

To see the dashboard instead of raw JSON, build the SPA once and reload the
same address:

```bash
cd web && npm install && npm run build
```

Live mode connects to real GCP, ClickHouse, and Parallel services. Copy
`.env.example` to `.env`, fill in every value, and run
`CLEARCUT_MODE=live python main.py`. A blank `OTEL_EXPORTER_OTLP_ENDPOINT=`
line in that copy counts as set, not empty, and starts an exporter that
retries against nothing. The mock demo above never touches this file, so
skip it there.
