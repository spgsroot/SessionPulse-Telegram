"""Account state machine with in-memory state and periodic persistence."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("session_pulse.state")

VALID_TRANSITIONS: dict[str, set[str]] = {
    "created": {"connecting"},
    "connecting": {"connected", "error"},
    "connected": {"monitoring", "stopped", "error"},
    "monitoring": {"throttled", "recovering", "stopped", "error", "banned"},
    "throttled": {"monitoring", "stopped", "error"},
    "recovering": {"monitoring", "stopped", "error"},
    "stopped": {"connecting", "monitoring", "deleted"},
    "error": {"connecting", "monitoring", "deleted"},
    "banned": set(),
    "deleted": set(),
}

# States allowed as initial (account not yet tracked)
_INITIAL_STATES = {"created", "connecting", "connected", "monitoring", "stopped", "error"}


@dataclass
class AccountStateEntry:
    phone: str
    state: str
    previous_state: str = ""
    state_since: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    error_message: str = ""
    metadata: dict = field(default_factory=dict)
    last_event_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    messages_1m: float = 0
    messages_5m: float = 0
    messages_15m: float = 0
    reactions_1m: float = 0
    errors_1h: int = 0
    reconnects_24h: int = 0
    active_channels: int = 0


class AccountStateMachine:
    def __init__(self, storage):
        self._states: dict[str, AccountStateEntry] = {}
        self._dirty: set[str] = set()
        self._storage = storage
        self._ws_manager = None
        self._lock = asyncio.Lock()

    def set_ws_manager(self, ws_manager) -> None:
        self._ws_manager = ws_manager

    async def load_from_storage(self) -> int:
        rows = await self._storage.get_all_account_states()
        for row in rows:
            state_since = row.get("state_since")
            if isinstance(state_since, str):
                try:
                    state_since = datetime.fromisoformat(state_since)
                except (ValueError, TypeError):
                    state_since = datetime.now(timezone.utc)
            elif not isinstance(state_since, datetime):
                state_since = datetime.now(timezone.utc)

            last_event = row.get("last_event_at")
            if isinstance(last_event, str):
                try:
                    last_event = datetime.fromisoformat(last_event)
                except (ValueError, TypeError):
                    last_event = datetime.now(timezone.utc)
            elif not isinstance(last_event, datetime):
                last_event = datetime.now(timezone.utc)

            self._states[row["phone"]] = AccountStateEntry(
                phone=row["phone"],
                state=row["state"],
                previous_state=row.get("previous_state", ""),
                state_since=state_since,
                error_message=row.get("error_message", ""),
                last_event_at=last_event,
            )
        logger.info(f"Loaded {len(self._states)} account states from storage")
        return len(self._states)

    async def transition(
        self, phone: str, new_state: str, **kwargs
    ) -> bool:
        current = self._states.get(phone)
        current_state = current.state if current else None

        # New account
        if current_state is None:
            if new_state not in _INITIAL_STATES:
                return False
            entry = AccountStateEntry(
                phone=phone,
                state=new_state,
                error_message=kwargs.get("error", ""),
                metadata=kwargs.get("metadata", {}),
            )
            self._states[phone] = entry
            self._dirty.add(phone)
            await self._broadcast_change(phone, "", new_state, **kwargs)
            return True

        # Idempotent: same state → just update last_event
        if current_state == new_state:
            current.last_event_at = datetime.now(timezone.utc)
            return True

        # Validate transition
        allowed = VALID_TRANSITIONS.get(current_state, set())
        if new_state not in allowed:
            logger.warning(
                f"Invalid transition: {phone} {current_state} -> {new_state}"
            )
            return False

        old_state = current_state
        current.previous_state = old_state
        current.state = new_state
        current.state_since = datetime.now(timezone.utc)
        current.error_message = kwargs.get("error", "")
        current.metadata = kwargs.get("metadata", {})
        self._dirty.add(phone)

        await self._broadcast_change(phone, old_state, new_state, **kwargs)
        return True

    def update_last_event(self, phone: str, timestamp: str = "") -> None:
        entry = self._states.get(phone)
        if entry:
            entry.last_event_at = datetime.now(timezone.utc)

    def update_metrics(
        self, phone: str, metric_name: str, value: float
    ) -> None:
        entry = self._states.get(phone)
        if not entry:
            return
        if metric_name == "messages_received":
            entry.messages_1m = value
        elif metric_name == "reactions_received":
            entry.reactions_1m = value

    def get_all_states(self) -> list[dict]:
        return [
            {
                "phone": e.phone,
                "state": e.state,
                "previous_state": e.previous_state,
                "state_since": e.state_since.isoformat(),
                "error_message": e.error_message,
                "last_event_at": e.last_event_at.isoformat(),
                "metrics": {
                    "messages_1m": e.messages_1m,
                    "messages_5m": e.messages_5m,
                    "messages_15m": e.messages_15m,
                    "reactions_1m": e.reactions_1m,
                    "errors_1h": e.errors_1h,
                    "active_channels": e.active_channels,
                },
            }
            for e in self._states.values()
        ]

    def get_state(self, phone: str) -> dict | None:
        e = self._states.get(phone)
        if not e:
            return None
        return {
            "phone": e.phone,
            "state": e.state,
            "previous_state": e.previous_state,
            "state_since": e.state_since.isoformat(),
            "error_message": e.error_message,
            "last_event_at": e.last_event_at.isoformat(),
            "metadata": e.metadata,
            "metrics": {
                "messages_1m": e.messages_1m,
                "messages_5m": e.messages_5m,
                "messages_15m": e.messages_15m,
                "reactions_1m": e.reactions_1m,
                "errors_1h": e.errors_1h,
                "active_channels": e.active_channels,
                "reconnects_24h": e.reconnects_24h,
            },
        }

    def get_summary(self) -> dict:
        by_state: dict[str, int] = {}
        for e in self._states.values():
            by_state[e.state] = by_state.get(e.state, 0) + 1
        return {"total": len(self._states), "by_state": by_state}

    async def flush_loop(self, interval: float = 10.0) -> None:
        while True:
            await asyncio.sleep(interval)
            await self._flush_dirty()

    async def _flush_dirty(self) -> None:
        async with self._lock:
            if not self._dirty:
                return
            entries = [
                self._states[p]
                for p in self._dirty
                if p in self._states
            ]
            self._dirty.clear()

        try:
            await self._storage.upsert_account_states(entries)
        except Exception as e:
            logger.error(f"Failed to flush account states: {e}")
            async with self._lock:
                for entry in entries:
                    self._dirty.add(entry.phone)

    async def _broadcast_change(
        self, phone: str, old_state: str, new_state: str, **kwargs
    ) -> None:
        if not self._ws_manager:
            return
        try:
            await self._ws_manager.broadcast(
                "accounts",
                {
                    "type": "state_change",
                    "phone": phone,
                    "previous_state": old_state,
                    "new_state": new_state,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error": kwargs.get("error", ""),
                },
            )
        except Exception as e:
            logger.debug(f"WS broadcast error: {e}")
