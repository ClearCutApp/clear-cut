# Architecture decision records

One numbered record per decision that was expensive to make and would be
expensive to reverse. The number sequence is global; the subdirectory says which
kind of decision it was, not which sequence it belongs to.

A record is never edited to change its mind. It is amended in place under a
dated `## Amendment` heading when the world moved, or superseded by a later
record that names it. An ADR that quietly rewrites its own decision stops being
a record.

## Read these first

The [approved specification](../../recovery/specification.md) and
[ADR 0016](architecture/0016-production-recovery.md) govern current recovery.
The [dated situation](../../recovery/situation-2026-09-07.md) records implementation
and live-evidence gaps; an accepted ADR does not prove deployment.

- **0001** — the product is ClearCut. `IP Guardian` survives only as a
  historical name inside `docs/resources/`.
- **0006 / 0016** — root [AGENTS.md](../../../AGENTS.md) and the approved
  specification govern the current hexagonal layout under `src/clearcut/`.
  Historical `.claude/AGENT.md` and flat `app.py` diagrams do not override them.
- **0016** — Firestore owns transactional identity/workspace state; Cloud Run
  Jobs own durable execution; ClickHouse serves outbox-fed analytics/history.

Everything under `docs/resources/` predates the current build. Where it
disagrees with an ADR, the ADR is right.

## Product

| # | Decision | Status |
|---|---|---|
| [0001](product/0001-product-name-clearcut.md) | The product is ClearCut | Accepted |
| [0003](product/0003-partner-track-parallel.md) | Enter the Parallel partner track | Accepted |
| [0011](product/0011-submission-runs-live-on-the-analyze-path.md) | The submission runs live on the analyze path | Accepted, cut reversed by 0012 |
| [0012](product/0012-api-partitioned-by-domain.md) | The API is partitioned by domain, and the cut endpoints come back | Accepted, amends 0011 |

## Architecture

| # | Decision | Status |
|---|---|---|
| [0002](architecture/0002-gemini-model-pins.md) | Pin Gemini 3 model IDs | Accepted, amended 2026-09-03 and 2026-09-05 |
| [0004](architecture/0004-lore-bigquery-vectorstore.md) | Lore vectors live in BigQuery | Accepted |
| [0005](architecture/0005-territorial-grounding-datastore.md) | One Vertex AI Search store, filtered per jurisdiction | Accepted |
| [0006](architecture/0006-hexagonal-architecture.md) | Hexagonal layout under `src/clearcut/` | Accepted |
| [0007](architecture/0007-incremental-delta-by-scene-hash.md) | Delta re-analysis by scene hash | Accepted, amended 2026-08-31 |
| [0009](architecture/0009-frontend-react-spa.md) | React and Vite SPA | Accepted, stale on styling |
| [0010](architecture/0010-hosting-cloud-run.md) | Host on Cloud Run | Accepted |
| [0013](architecture/0013-analysis-is-a-job-resource.md) | Analysis is a job resource, not a blocking request | Accepted |
| [0014](architecture/0014-findings-are-durable-and-the-tracker-key-is-wrong.md) | Findings are durable, and the tracker key is wrong | Accepted |
| [0015](architecture/0015-highlight-spans-are-computed-in-the-domain.md) | Highlight spans are computed in the domain | Accepted |
| [0016](architecture/0016-production-recovery.md) | Production identity and durable workspace state | Accepted; implementation substantial, deployed acceptance pending |

## Observability

| # | Decision | Status |
|---|---|---|
| [0008](observability/0008-observability-grafana-otel.md) | OpenTelemetry to Grafana Cloud | Accepted, unfulfilled |

## Known stale content

Recorded here rather than silently fixed, because an ADR is a record of what was
decided and when.

- **0009** specifies Tailwind. The dependency was never added; the frontend
  styles with vanilla CSS over design tokens in `web/src/styles/`. It also
  describes three surfaces, which became six routed views. The framework and
  build tool it picks are still what ships.
- **0008** remains a launch requirement. Historical CP-058 credential claims are
  not current environment evidence. Verify dated receiver-side Grafana evidence
  against the present deployment; see the current situation report.
