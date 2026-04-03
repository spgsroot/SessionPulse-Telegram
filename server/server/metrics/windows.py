"""Rolling window metric calculator."""

import logging
import time
from collections import deque
from datetime import datetime

logger = logging.getLogger("session_pulse.metrics")

WINDOWS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
}


class RollingWindowCalculator:
    def __init__(self):
        self._data: dict[str, deque[tuple[float, float]]] = {}

    def add_sample(
        self, key: str, value: float, timestamp: str | float | None = None
    ) -> None:
        ts = _parse_ts(timestamp)
        if key not in self._data:
            self._data[key] = deque(maxlen=3600)
        self._data[key].append((ts, value))

    def get_rate(self, key: str, window: str) -> float:
        seconds = WINDOWS.get(window, 60)
        cutoff = time.time() - seconds
        samples = self._data.get(key)
        if not samples:
            return 0.0
        total = sum(v for ts, v in samples if ts >= cutoff)
        return total / seconds

    def get_sum(self, key: str, window: str) -> float:
        seconds = WINDOWS.get(window, 60)
        cutoff = time.time() - seconds
        samples = self._data.get(key)
        if not samples:
            return 0.0
        return sum(v for ts, v in samples if ts >= cutoff)

    def get_count(self, key: str, window: str) -> int:
        seconds = WINDOWS.get(window, 60)
        cutoff = time.time() - seconds
        samples = self._data.get(key)
        if not samples:
            return 0
        return sum(1 for ts, _ in samples if ts >= cutoff)

    def get_percentile(self, key: str, window: str, pct: float) -> float:
        seconds = WINDOWS.get(window, 60)
        cutoff = time.time() - seconds
        values = sorted(
            v for ts, v in (self._data.get(key) or []) if ts >= cutoff
        )
        if not values:
            return 0.0
        idx = int(len(values) * pct / 100)
        return values[min(idx, len(values) - 1)]

    def get_account_metrics(self, phone: str) -> dict:
        prefix = f"account:{phone}:"
        result = {}
        for key in self._data:
            if key.startswith(prefix):
                metric_name = key[len(prefix):]
                result[metric_name] = {
                    w: self.get_sum(key, w) for w in WINDOWS
                }
        return result

    def cleanup(self) -> int:
        cutoff = time.time() - 3600
        removed = 0
        for key in list(self._data.keys()):
            samples = self._data[key]
            while samples and samples[0][0] < cutoff:
                samples.popleft()
                removed += 1
            if not samples:
                del self._data[key]
        return removed


def _parse_ts(ts) -> float:
    if ts is None:
        return time.time()
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(
                ts.replace("Z", "+00:00")
            ).timestamp()
        except (ValueError, TypeError):
            return time.time()
    if isinstance(ts, datetime):
        return ts.timestamp()
    return time.time()
