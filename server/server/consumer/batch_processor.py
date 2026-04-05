"""Routes observability events to appropriate handlers."""

import json
import logging

logger = logging.getLogger("session_pulse.processor")


class BatchProcessor:
    def __init__(self, state_machine, metrics, alerts, ws_manager, storage):
        self._sm = state_machine
        self._metrics = metrics
        self._alerts = alerts
        self._ws = ws_manager
        self._storage = storage

    async def process_batch(self, events: list[dict]) -> None:
        for event in events:
            try:
                event_type = event.get("event_type", "")
                if event_type == "state_change":
                    await self._handle_state_change(event)
                elif event_type == "metric":
                    await self._handle_metric(event)
                elif event_type == "event":
                    await self._handle_event(event)
                elif event_type == "span":
                    self._handle_span(event)
            except Exception as e:
                logger.error(f"Error processing event: {e}")

        # Batch persist all events
        try:
            await self._storage.insert_events(events)
        except Exception as e:
            logger.error(f"Failed to persist events: {e}")

        # Evaluate alerts
        try:
            await self._alerts.evaluate(self._sm, self._metrics)
        except Exception as e:
            logger.error(f"Alert evaluation error: {e}")

    async def _handle_state_change(self, event: dict) -> None:
        phone = event.get("entity_id", "")
        new_state = event.get("new_state", "")
        error = event.get("error_message", "")

        metadata = {}
        payload_str = event.get("payload", "{}")
        if isinstance(payload_str, str):
            try:
                metadata = json.loads(payload_str)
            except (json.JSONDecodeError, TypeError):
                pass
        elif isinstance(payload_str, dict):
            metadata = payload_str

        await self._sm.transition(
            phone, new_state, error=error, metadata=metadata
        )

    async def _handle_metric(self, event: dict) -> None:
        entity_type = event.get("entity_type", "")
        entity_id = event.get("entity_id", "")
        metric_name = event.get("metric_name", "")
        metric_value = float(event.get("metric_value", 0))
        timestamp = event.get("timestamp")

        key = f"{entity_type}:{entity_id}:{metric_name}"
        self._metrics.add_sample(key, metric_value, timestamp)

        if entity_type == "account":
            await self._sm.update_last_event(entity_id)
            # Update state machine with rolling rates (not raw values)
            rate_1m = self._metrics.get_rate(key, "1m")
            rate_5m = self._metrics.get_rate(key, "5m")
            rate_15m = self._metrics.get_rate(key, "15m")
            self._sm.update_metrics(entity_id, metric_name, rate_1m, rate_5m, rate_15m)

    async def _handle_event(self, event: dict) -> None:
        entity_id = event.get("entity_id", "")
        if event.get("entity_type") == "account":
            await self._sm.update_last_event(entity_id)

        try:
            await self._ws.broadcast(
                f"timeline:{entity_id}",
                {"type": "event", "event": event},
            )
        except Exception:
            pass

    def _handle_span(self, event: dict) -> None:
        name = event.get("event_name", "")
        duration = float(event.get("duration_ms", 0))
        if name and duration > 0:
            key = f"span:{name}:duration_ms"
            self._metrics.add_sample(
                key, duration, event.get("timestamp")
            )
