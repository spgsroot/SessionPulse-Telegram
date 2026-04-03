"""Event buffering: BatchBuffer for accumulation, RingBuffer for overflow."""

import asyncio
import contextlib
import logging
import time
from collections import deque
from typing import Awaitable, Callable

logger = logging.getLogger("session_pulse.buffer")


class BatchBuffer:
    """Accumulates events and flushes by size or time.

    Flush triggers:
    - len(buffer) >= buffer_size
    - Time since last flush >= flush_interval
    """

    __slots__ = (
        "_buffer",
        "_lock",
        "_buffer_size",
        "_flush_interval",
        "_flush_callback",
        "_task",
        "_last_flush",
        "_running",
    )

    def __init__(
        self,
        buffer_size: int = 1000,
        flush_interval_ms: int = 5000,
        flush_callback: Callable[[list[dict]], Awaitable[bool]] | None = None,
    ):
        self._buffer: list[dict] = []
        self._lock = asyncio.Lock()
        self._buffer_size = buffer_size
        self._flush_interval = flush_interval_ms / 1000.0
        self._flush_callback = flush_callback
        self._task: asyncio.Task | None = None
        self._last_flush = time.monotonic()
        self._running = False

    def add(self, event: dict) -> None:
        """Non-blocking append. Called from emit() in hot path."""
        self._buffer.append(event)

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._flush_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        # Final flush
        await self._flush()

    async def _flush_loop(self) -> None:
        while self._running:
            await asyncio.sleep(1.0)
            now = time.monotonic()
            should_flush = len(self._buffer) >= self._buffer_size or (
                self._buffer and (now - self._last_flush) >= self._flush_interval
            )
            if should_flush:
                await self._flush()

    async def _flush(self) -> list[dict]:
        """Swap buffer and send. Returns unflushed events on failure."""
        async with self._lock:
            if not self._buffer:
                return []
            batch = self._buffer
            self._buffer = []
            self._last_flush = time.monotonic()

        if self._flush_callback:
            try:
                success = await self._flush_callback(batch)
                if not success:
                    return batch
            except Exception as e:
                logger.error(f"Flush callback error: {e}")
                return batch
        return []

    def __len__(self) -> int:
        return len(self._buffer)


class RingBuffer:
    """Circular overflow buffer for failed events.

    Uses deque(maxlen=N) for O(1) operations.
    Oldest events evicted when full.
    """

    __slots__ = ("_buffer", "_dropped_count", "_maxlen")

    def __init__(self, maxlen: int = 10000):
        self._buffer: deque[dict] = deque(maxlen=maxlen)
        self._dropped_count: int = 0
        self._maxlen = maxlen

    def extend(self, events: list[dict]) -> int:
        """Add events. Returns number of dropped (evicted) events."""
        before = len(self._buffer)
        self._buffer.extend(events)
        after = len(self._buffer)
        expected = before + len(events)
        dropped = max(0, expected - self._maxlen)
        self._dropped_count += dropped
        return dropped

    def drain(self) -> list[dict]:
        """Remove and return all events for retry."""
        events = list(self._buffer)
        self._buffer.clear()
        return events

    @property
    def dropped_total(self) -> int:
        return self._dropped_count

    def __len__(self) -> int:
        return len(self._buffer)
