"""Run one per-item lookup over a bounded thread pool, in input order.

Both pipeline use cases enrich each deduped finding with two blocking HTTPS
calls -- `LegalGrounding.ground` and `RightsResearch.find`. Serially, a
five-finding script pays those round trips one after another, and the Parallel
Task API `core` processor alone takes 77-169s per run, so the wait is measured
in minutes rather than seconds. The lookups for two different findings share
nothing, so they are the one part of the pipeline that can overlap.

`concurrent.futures` is the standard library, so this stays a plain
application-layer helper: it crosses no I/O boundary of its own and gets no
port. AGENT.md Section 4 bans an interface whose only implementation stays
in-process, and a `Protocol` over "run these callables" would be exactly that.
The one thing that *is* injected is `ContextBinder`, and the layer rule below
is why.

The precedent for a small shared helper here is `grounding_query.py`: two use
cases needed the same thing, so it lives beside them rather than being typed
out twice.
"""

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Protocol, TypeVar

_T = TypeVar("_T")
_R = TypeVar("_R")

# Four threads, fixed, not constructor config (AGENT.md Section 4) -- and not
# a rate-limit guard, which it is sometimes mistaken for. Parallel allows
# 2,000 task POSTs per minute, and the `GET /v1/tasks/runs/{id}` polling the
# SDK's blocking `result()` does is exempt from the quota entirely, so four
# threads are nowhere near a 429.
#
# The real bound is Parallel's own queue: runs execute concurrently but the
# capacity behind them is finite, so a burst wider than that capacity simply
# queues, and end-to-end time drifts past the published p50s -- more threads
# stop buying latency. Four is chosen against that diminishing return, plus
# the thread stacks and open TLS connections a 512Mi Cloud Run container pays
# for. These are blocking HTTPS waits rather than CPU work, so `cpu: 1000m`
# does not bound the number.
_MAX_WORKERS = 4


class ContextBinder(Protocol):
    """Carries the calling thread's ambient context into a worker thread.

    Injected rather than done here because `application/` may not import
    `opentelemetry` (AGENT.md Section 2 rule 2, enforced by
    `tests/unit/test_layer_boundaries.py`). A `ThreadPoolExecutor` worker
    starts with an empty OpenTelemetry context, so the `ground` and `research`
    spans the adapters open inside it would each become a *root* span with its
    own trace id -- one run would arrive in Grafana as five unrelated traces
    instead of one. `composition.bind_context` is the implementation; the
    identity `run_unbound` below is the default.
    """

    def __call__(self, work: Callable[[], _R]) -> Callable[[], _R]: ...


def run_unbound(work: Callable[[], _R]) -> Callable[[], _R]:
    """The default binder: hand the work back untouched.

    A run nobody is tracing is still a correct run, so nothing here may
    require a context to exist.
    """
    return work


def _invoke(work: Callable[[], _R]) -> _R:
    """All a pool worker does: call what the calling thread already bound."""
    return work()


def map_bounded(work: Callable[[_T], _R], items: Sequence[_T], bind: ContextBinder) -> list[_R]:
    """`[work(item) for item in items]`, on at most `_MAX_WORKERS` threads,
    returned in input order.

    Zero or one item never opens a pool: a `ThreadPoolExecutor` around a
    single blocking call adds a thread hand-off and buys no overlap.

    `bind` is applied here, before the pool exists, because this is the only
    place the caller's context can still be read: a binder invoked from
    inside a worker would capture that worker's own empty context and carry
    nothing across.

    `pool.map`, never `as_completed`: the caller mints `finding_id` as
    `EVT-NNN` from its own loop index (Decision D13), so a result list in
    completion order would renumber a project's findings by whichever lookup
    happened to answer first -- and `EvaluateDelta`'s carry-forward join reads
    those ids across versions.
    """
    if len(items) <= 1:
        return [work(item) for item in items]

    bound = [bind(partial(work, item)) for item in items]
    with ThreadPoolExecutor(
        max_workers=min(_MAX_WORKERS, len(items)), thread_name_prefix="clearcut-enrich"
    ) as pool:
        return list(pool.map(_invoke, bound))
