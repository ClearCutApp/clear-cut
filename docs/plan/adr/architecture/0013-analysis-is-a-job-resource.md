# ADR 0013: Analysis is a job resource, not a blocking request

Status: Accepted
Date: 2026-09-05

## Context

`POST /api/projects/{id}/scripts` runs the whole pipeline inside the request and
returns when it finishes. On real services that is twelve to twenty minutes.
`tests/live/test_end_to_end_live.py` records `1 passed in 870.64s`, and the
Parallel rights lookup alone takes 77 to 169 seconds per finding, sequentially,
once per deduplicated finding.

The system already carries the scar. `Dockerfile` sets gunicorn `--timeout 0`
and the Cloud Run request timeout was raised past 300 seconds, both so a
request could stay open long enough to finish. That worked while the client was
`curl` and a human waiting for a demo.

It does not work for a web product. A browser tab, a load balancer, a corporate
proxy and a phone changing networks all give up long before twenty minutes, and
none of them tell the server. The user gets a spinner that ends in a network
error while the work either completed invisibly or died halfway. There is no
progress, no retry, no way to ask what happened, and no way to leave and come
back.

D80 ruled analysis stays synchronous for the API partition round. That ruling
was scoped to a submission. It does not survive the product goal.

## Decision

`POST /api/projects/{id}/scripts` returns **202 Accepted** with
`Location: /api/projects/{id}/analyses/{analysis_id}`. The client polls that
path. `GET .../analyses/{analysis_id}` returns the job with its state, and the
analysis result once the state is `SUCCEEDED`.

`AnalysisJob` is a domain aggregate with four states -- `QUEUED`, `RUNNING`,
`SUCCEEDED`, `FAILED` -- and immutable transitions at `version + 1`, the same
shape `TrackerItem` already uses. `SUCCEEDED` and `FAILED` are terminal and
raise on re-entry. Unlike a tracker transition, which is an audit record of a
producer's action and legal in every direction, these states describe work that
has finished; letting a finished job re-enter `RUNNING` would be a lie about
what ran.

The job row in ClickHouse is the source of truth, not process memory. The work
runs in a background thread in the same gunicorn process, with Cloud Run at
`min-instances=1` and `--no-cpu-throttling` so the instance is not reclaimed or
frozen between requests.

`AnalysisJob.is_stale(now, after)` is a pure predicate that a read uses to reap
a job left `RUNNING` past a deadline. Without it, an instance that dies mid-run
leaves a row that says `RUNNING` forever and a client that polls forever.

`AnalysisJob` carries timezone-aware `datetime`, not the preformatted string
`TrackerItem.updated_at` uses. The reaper compares times, and a string cannot be
compared without reparsing it in the layer that is meant to hold no format.
`datetime` is stdlib, so the domain rule holds. Adapters format on the way out.

## Consequences

A producer can upload a script, close the tab, and come back to a finished
analysis. That is the whole point, and it is not achievable any other way.

The failure mode moves rather than disappearing. A Cloud Run instance reclaimed
mid-run loses that run; the reaper marks the job `FAILED` on the next read and
the producer re-submits. That is a worse outcome than a durable queue and a
better one than a request that hangs until a proxy kills it. The honest fix is
Cloud Tasks with a worker endpoint, and it is deferred on purpose: it adds a
queue, an IAM binding, a retry policy and a second entry point, for a failure
that `min-instances=1` makes uncommon.

`min-instances=1` costs money continuously rather than per request. Cloud Run at
zero was free between demos; it no longer is.

The web client gains a polling loop and three states to render. Every screen
that shows an analysis now has a "still working" state, which the design target
does not draw. That gap is real and belongs to the UI work, not here.

Revisit this the first time a run is lost in production, or the first time two
producers analyze at once and the single instance serializes them.
