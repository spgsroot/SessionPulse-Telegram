"""Circuit breaker for transport fault tolerance."""

import logging
import time
from enum import Enum
from typing import Awaitable, Callable

logger = logging.getLogger("session_pulse.circuit_breaker")


class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """3-state circuit breaker.

    - CLOSED: normal, track failures
    - OPEN: reject calls, wait for recovery_timeout
    - HALF_OPEN: allow test calls, close after success_threshold
    """

    __slots__ = (
        "_state",
        "_failure_count",
        "_success_count",
        "_last_failure_time",
        "_failure_threshold",
        "_recovery_timeout",
        "_success_threshold",
    )

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 3,
    ):
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._success_threshold = success_threshold

    async def call(
        self, func: Callable[..., Awaitable], *args, **kwargs
    ) -> bool:
        """Execute function through circuit breaker. Returns success/failure."""
        if self._state == CircuitBreakerState.OPEN:
            if (
                time.monotonic() - self._last_failure_time
                >= self._recovery_timeout
            ):
                self._state = CircuitBreakerState.HALF_OPEN
                self._success_count = 0
                logger.info("Circuit breaker: OPEN → HALF_OPEN")
            else:
                return False

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            logger.debug(f"Circuit breaker: call failed: {e}")
            return False

    def _on_success(self) -> None:
        if self._state == CircuitBreakerState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self._success_threshold:
                self._state = CircuitBreakerState.CLOSED
                self._failure_count = 0
                logger.info("Circuit breaker: HALF_OPEN → CLOSED")
        elif self._state == CircuitBreakerState.CLOSED:
            self._failure_count = 0

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._failure_threshold:
            prev = self._state
            self._state = CircuitBreakerState.OPEN
            if prev != CircuitBreakerState.OPEN:
                logger.warning(
                    f"Circuit breaker: {prev.value} → OPEN "
                    f"(after {self._failure_count} failures)"
                )

    @property
    def state(self) -> CircuitBreakerState:
        return self._state
