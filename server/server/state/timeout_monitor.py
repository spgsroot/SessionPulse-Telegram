"""Detects stale accounts and triggers automatic state transitions."""

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger("session_pulse.timeout")


def _ensure_aware(dt: datetime) -> datetime:
    """Convert naive datetime to UTC-aware."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class TimeoutMonitor:
    def __init__(
        self,
        state_machine,
        heartbeat_timeout: float = 60.0,
        max_recover_time: float = 3600.0,
        check_interval: float = 10.0,
    ):
        self._sm = state_machine
        self._heartbeat_timeout = heartbeat_timeout
        self._max_recover_time = max_recover_time
        self._check_interval = check_interval
        self._running = True

    async def run(self) -> None:
        while self._running:
            await asyncio.sleep(self._check_interval)
            now = datetime.now(timezone.utc)
            for phone, entry in list(self._sm._states.items()):
                try:
                    await self._check_entry(phone, entry, now)
                except Exception as e:
                    logger.error(f"Timeout check error for {phone}: {e}")

    async def _check_entry(self, phone, entry, now) -> None:
        if entry.state == "monitoring":
            age = (now - _ensure_aware(entry.last_event_at)).total_seconds()
            if age > self._heartbeat_timeout:
                await self._sm.transition(
                    phone,
                    "recovering",
                    error=f"No heartbeat for {age:.0f}s",
                )

        elif entry.state == "recovering":
            recover_age = (now - _ensure_aware(entry.state_since)).total_seconds()
            if recover_age > self._max_recover_time:
                await self._sm.transition(
                    phone,
                    "error",
                    error=f"Recovery timeout after {recover_age:.0f}s",
                )

        elif entry.state == "throttled":
            flood_wait = 0
            if isinstance(entry.metadata, dict):
                flood_wait = entry.metadata.get("flood_wait_seconds", 0)
            throttle_age = (now - _ensure_aware(entry.state_since)).total_seconds()
            if flood_wait > 0 and throttle_age >= flood_wait:
                await self._sm.transition(phone, "monitoring")

    def stop(self) -> None:
        self._running = False
