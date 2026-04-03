"""SessionPulse client — central emission engine."""

import asyncio
import contextlib
import functools
import inspect
import json
import logging
import random
import time
from typing import Any

from .core.buffer import BatchBuffer, RingBuffer
from .core.circuit_breaker import CircuitBreaker
from .core.context import TraceContext
from .core.event import ObservabilityEvent
from .core.states import AccountState, Severity
from .transport.http import HttpTransport
from .transport.kafka import KafkaTransport
from .transport.noop import NoopTransport

logger = logging.getLogger("session_pulse")

# Fields that must never appear in observability events
_FORBIDDEN_PAYLOAD_FIELDS = frozenset(
    {"session_string", "api_hash", "password", "secret_key", "token"}
)


class SessionPulse:
    """Main SDK facade. Thread-safe, async, zero-impact on host service."""

    def __init__(
        self,
        service_name: str,
        transport: str = "noop",
        kafka_bootstrap: str = "",
        kafka_topic: str = "observability_events",
        http_endpoint: str = "",
        http_auth_token: str = "",
        buffer_size: int = 1000,
        flush_interval_ms: int = 5000,
        ring_buffer_size: int = 10000,
        sampling_rate: float = 1.0,
    ):
        self._service_name = service_name
        self._sampling_rate = sampling_rate
        self._account_states: dict[str, str] = {}

        # Transport
        self._transport = self._create_transport(
            transport,
            kafka_bootstrap,
            kafka_topic,
            http_endpoint,
            http_auth_token,
        )

        # Circuit breaker
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5, recovery_timeout=60.0, success_threshold=3
        )

        # Buffers
        self._ring_buffer = RingBuffer(maxlen=ring_buffer_size)
        self._batch_buffer = BatchBuffer(
            buffer_size=buffer_size,
            flush_interval_ms=flush_interval_ms,
            flush_callback=self._flush,
        )

        # Background retry task
        self._retry_task: asyncio.Task | None = None

        # Context
        TraceContext.set_service(service_name)

    @staticmethod
    def _create_transport(
        transport_type: str,
        kafka_bootstrap: str,
        kafka_topic: str,
        http_endpoint: str,
        http_auth_token: str,
    ):
        if transport_type == "kafka":
            return KafkaTransport(kafka_bootstrap, kafka_topic)
        elif transport_type == "http":
            return HttpTransport(http_endpoint, http_auth_token)
        else:
            return NoopTransport()

    # ── Lifecycle ──

    async def start(self) -> None:
        """Initialize transport and start background tasks."""
        try:
            await self._transport.start()
        except Exception as e:
            logger.error(f"Transport start failed, falling back to noop: {e}")
            self._transport = NoopTransport()
            await self._transport.start()

        await self._batch_buffer.start()
        self._retry_task = asyncio.create_task(self._retry_loop())
        logger.info(
            f"SessionPulse started (service={self._service_name}, "
            f"transport={type(self._transport).__name__})"
        )

    async def stop(self) -> None:
        """Flush remaining events and stop."""
        if self._retry_task:
            self._retry_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._retry_task

        await self._batch_buffer.stop()

        # Final retry of ring buffer
        if len(self._ring_buffer) > 0:
            events = self._ring_buffer.drain()
            try:
                await self._transport.send_batch(events)
            except Exception:
                pass

        await self._transport.stop()
        logger.info("SessionPulse stopped")

    # ── Public API: State Tracking ──

    def account_state(
        self,
        phone: str,
        state: AccountState,
        error: str = "",
        metadata: dict | None = None,
    ) -> None:
        """Track account state transition."""
        previous = self._account_states.get(phone, "")
        self._account_states[phone] = state.value

        severity = "info"
        if state in (AccountState.ERROR, AccountState.BANNED):
            severity = "error"
        elif state in (AccountState.THROTTLED, AccountState.RECOVERING):
            severity = "warning"

        self._emit(
            ObservabilityEvent(
                service_name=self._service_name,
                entity_type="account",
                entity_id=phone,
                event_type="state_change",
                event_name="account_state_transition",
                severity=severity,
                previous_state=previous,
                new_state=state.value,
                error_message=error,
                payload=json.dumps(metadata or {}),
            )
        )

    # ── Public API: Metrics ──

    def counter(
        self,
        name: str,
        entity_type: str,
        entity_id: str,
        value: float = 1.0,
        tags: dict | None = None,
    ) -> None:
        """Increment counter metric."""
        self._emit(
            ObservabilityEvent(
                service_name=self._service_name,
                entity_type=entity_type,
                entity_id=entity_id,
                event_type="metric",
                metric_name=name,
                metric_value=value,
                metric_type="counter",
                tags=tags or {},
            )
        )

    def gauge(
        self,
        name: str,
        entity_type: str,
        entity_id: str,
        value: float,
        tags: dict | None = None,
    ) -> None:
        """Set gauge metric to current value."""
        self._emit(
            ObservabilityEvent(
                service_name=self._service_name,
                entity_type=entity_type,
                entity_id=entity_id,
                event_type="metric",
                metric_name=name,
                metric_value=value,
                metric_type="gauge",
                tags=tags or {},
            )
        )

    def histogram(
        self,
        name: str,
        entity_type: str,
        entity_id: str,
        value: float,
        tags: dict | None = None,
    ) -> None:
        """Record histogram sample (latency, size, etc.)."""
        self._emit(
            ObservabilityEvent(
                service_name=self._service_name,
                entity_type=entity_type,
                entity_id=entity_id,
                event_type="metric",
                metric_name=name,
                metric_value=value,
                metric_type="histogram",
                tags=tags or {},
            )
        )

    # ── Public API: Events ──

    def event(
        self,
        entity_type: str,
        entity_id: str,
        event_name: str,
        severity: Severity = Severity.INFO,
        message: str = "",
        payload: dict | None = None,
    ) -> None:
        """Emit structured event."""
        safe_payload = self._sanitize_payload(payload)
        self._emit(
            ObservabilityEvent(
                service_name=self._service_name,
                entity_type=entity_type,
                entity_id=entity_id,
                event_type="event",
                event_name=event_name,
                severity=severity.value,
                message=message,
                payload=json.dumps(safe_payload),
            )
        )

    # ── Decorators ──

    def track_latency(self, name: str, entity_type: str = "service"):
        """Decorator to track async function execution latency."""

        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                start = time.monotonic()
                try:
                    result = await func(*args, **kwargs)
                    elapsed = (time.monotonic() - start) * 1000
                    self.histogram(
                        name, entity_type, self._service_name, elapsed
                    )
                    return result
                except Exception as e:
                    elapsed = (time.monotonic() - start) * 1000
                    self.histogram(
                        name,
                        entity_type,
                        self._service_name,
                        elapsed,
                        tags={"error": type(e).__name__},
                    )
                    raise

            return wrapper

        return decorator

    def track_session(self, phone_param: str = "phone"):
        """Decorator to track session connect/disconnect lifecycle."""

        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                phone = self._extract_param(func, phone_param, args, kwargs)
                self.event(
                    "session", phone, "session_connect_attempt"
                )
                try:
                    result = await func(*args, **kwargs)
                    self.event("session", phone, "session_connected")
                    return result
                except Exception as e:
                    self.event(
                        "session",
                        phone,
                        "session_connect_failed",
                        severity=Severity.ERROR,
                        payload={"error": str(e)},
                    )
                    raise

            return wrapper

        return decorator

    # ── Context Manager (spans) ──

    @contextlib.asynccontextmanager
    async def span(
        self,
        name: str,
        entity_type: str = "operation",
        entity_id: str = "",
        tags: dict | None = None,
    ):
        """Context manager for tracing spans with duration measurement."""
        trace_id = TraceContext.ensure_trace()
        parent_span_id = TraceContext.get_span_id()
        span_id = TraceContext.new_span()
        start = time.monotonic()
        _tags = dict(tags) if tags else {}

        class SpanContext:
            def set_tag(self, key: str, value: Any) -> None:
                _tags[key] = str(value)

            def set_metric(self, key: str, value: float) -> None:
                _tags[f"metric:{key}"] = str(value)

        ctx = SpanContext()
        error_msg = ""
        severity = "info"
        try:
            yield ctx
        except Exception as e:
            error_msg = str(e)
            severity = "error"
            raise
        finally:
            elapsed = (time.monotonic() - start) * 1000
            self._emit(
                ObservabilityEvent(
                    service_name=self._service_name,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    event_type="span",
                    event_name=name,
                    severity=severity,
                    error_message=error_msg,
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=parent_span_id,
                    duration_ms=elapsed,
                    tags=_tags,
                )
            )

    # ── Internal ──

    def _emit(self, event: ObservabilityEvent) -> None:
        """Non-blocking event emission. Never raises. Never does I/O."""
        try:
            if self._sampling_rate < 1.0:
                if random.random() > self._sampling_rate:
                    return
            self._batch_buffer.add(event.to_dict())
        except Exception:
            pass  # Never impact host service

    async def _flush(self, batch: list[dict]) -> bool:
        """Flush batch through circuit breaker to transport."""
        success = await self._circuit_breaker.call(
            self._transport.send_batch, batch
        )
        if not success:
            dropped = self._ring_buffer.extend(batch)
            if dropped > 0:
                logger.debug(
                    f"SessionPulse: {dropped} events evicted from ring buffer"
                )
        return success

    async def _retry_loop(self) -> None:
        """Periodically retry events from ring buffer."""
        while True:
            await asyncio.sleep(30.0)
            if len(self._ring_buffer) > 0 and self._transport.is_healthy():
                events = self._ring_buffer.drain()
                try:
                    success = await self._transport.send_batch(events)
                    if not success:
                        self._ring_buffer.extend(events)
                except Exception:
                    self._ring_buffer.extend(events)

    @staticmethod
    def _sanitize_payload(payload: dict | None) -> dict:
        if not payload:
            return {}
        return {
            k: v
            for k, v in payload.items()
            if k not in _FORBIDDEN_PAYLOAD_FIELDS
        }

    @staticmethod
    def _extract_param(
        func, param_name: str, args: tuple, kwargs: dict
    ) -> str:
        if param_name in kwargs:
            return str(kwargs[param_name])
        try:
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            if param_name in params:
                idx = params.index(param_name)
                if idx < len(args):
                    return str(args[idx])
        except (ValueError, TypeError):
            pass
        return ""
