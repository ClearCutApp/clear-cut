"""Unit tests for `clearcut.application.concurrency` (Change B).

`map_bounded` is the pre-pass both pipeline use cases run before their
sequential loop, so the two properties the loop depends on are the two pinned
hardest here: results come back in input order whatever order the work
finished in, and one item's exception is the caller's exception.

No `unittest.mock` (AGENT.md Section 5): every collaborator below is a plain
function or a hand-written recorder.
"""

import threading
import time
from collections.abc import Callable
from typing import TypeVar

import pytest

from clearcut.application.concurrency import map_bounded, run_unbound

_R = TypeVar("_R")


def _inverted_latency(index: int) -> str:
    """Item 0 sleeps longest, the last sleeps least -- so a `as_completed`
    implementation would hand back its results reversed, and only an
    order-preserving one can satisfy the assertions below."""
    time.sleep((5 - index) * 0.01)
    return f"item-{index}"


def test_results_come_back_in_input_order_not_completion_order() -> None:
    results = map_bounded(_inverted_latency, [0, 1, 2, 3, 4], run_unbound)

    assert results == ["item-0", "item-1", "item-2", "item-3", "item-4"]


def test_a_single_item_runs_on_the_calling_thread() -> None:
    """No pool for one item: a `ThreadPoolExecutor` spun up to run one
    blocking call buys nothing and moves the work off the thread whose
    context the caller bound."""
    caller = threading.current_thread()

    threads = map_bounded(lambda _: threading.current_thread(), [1], run_unbound)

    assert threads == [caller]


def test_an_empty_input_runs_nothing_and_returns_nothing() -> None:
    calls: list[int] = []

    def _record(item: int) -> int:
        calls.append(item)
        return item

    assert map_bounded(_record, [], run_unbound) == []
    assert calls == []


def test_an_exception_from_the_first_item_reaches_the_caller() -> None:
    """The D23 degrade-one-finding rule lives in the use case's own
    `except EnrichmentMissing`, not here: anything the pool did not catch is
    a hard failure, and swallowing it would publish a partial report as a
    complete one."""

    def _raise_on_zero(item: int) -> int:
        if item == 0:
            raise ValueError("item 0 failed")
        time.sleep(0.01)
        return item

    with pytest.raises(ValueError, match="item 0 failed"):
        map_bounded(_raise_on_zero, [0, 1, 2], run_unbound)


def test_run_unbound_returns_the_callable_unchanged() -> None:
    """The identity default: a run nobody is tracing must not pay for a
    wrapper, and must not change what the work returns."""

    def _work() -> str:
        return "done"

    assert run_unbound(_work) is _work


def test_the_binder_runs_on_the_calling_thread_once_per_item() -> None:
    """The property `composition.bind_context` depends on entirely.

    It captures the ambient context at the moment it is called, so calling it
    from inside a worker would capture that worker's empty context and carry
    nothing across -- the pool would still detach every span, silently, with
    a binder wired and every other assertion here still green.
    """
    caller = threading.current_thread()
    binder_threads: list[threading.Thread] = []
    lock = threading.Lock()

    def _recording_bind(work: Callable[[], _R]) -> Callable[[], _R]:
        with lock:
            binder_threads.append(threading.current_thread())
        return work

    results = map_bounded(lambda item: item * 2, [1, 2, 3], _recording_bind)

    assert results == [2, 4, 6]
    assert binder_threads == [caller, caller, caller]
