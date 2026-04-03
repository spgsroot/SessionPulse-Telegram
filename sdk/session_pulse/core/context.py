"""Trace context propagation using contextvars."""

import contextvars
import uuid

_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "pulse_trace_id", default=""
)
_span_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "pulse_span_id", default=""
)
_service_name: contextvars.ContextVar[str] = contextvars.ContextVar(
    "pulse_service_name", default=""
)


class TraceContext:
    @staticmethod
    def get_trace_id() -> str:
        return _trace_id.get()

    @staticmethod
    def get_span_id() -> str:
        return _span_id.get()

    @staticmethod
    def get_service_name() -> str:
        return _service_name.get()

    @staticmethod
    def set_service(name: str) -> None:
        _service_name.set(name)

    @staticmethod
    def new_span() -> str:
        span = uuid.uuid4().hex[:16]
        _span_id.set(span)
        return span

    @staticmethod
    def set_trace(trace_id: str) -> None:
        _trace_id.set(trace_id)

    @staticmethod
    def ensure_trace() -> str:
        tid = _trace_id.get()
        if not tid:
            tid = uuid.uuid4().hex[:16]
            _trace_id.set(tid)
        return tid
