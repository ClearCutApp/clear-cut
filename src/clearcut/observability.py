"""Provider exceptions may contain screenplay text; traces only record safe status."""

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


@contextmanager
def stage_span(tracer: trace.Tracer, name: str) -> Iterator[trace.Span]:
    with tracer.start_as_current_span(
        name, record_exception=False, set_status_on_exception=False
    ) as span:
        try:
            yield span
        except Exception:
            span.set_status(Status(StatusCode.ERROR, "stage failed"))
            raise
