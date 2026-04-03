"""Basic SessionPulse SDK usage example.

This example shows how to integrate SessionPulse into any Python async service.
"""

import asyncio

from session_pulse import AccountState, SessionPulse, Severity


async def main():
    # Initialize with Kafka transport (use "noop" to disable)
    pulse = SessionPulse(
        service_name="my-service",
        transport="kafka",
        kafka_bootstrap="localhost:9092",
        kafka_topic="observability_events",
    )
    await pulse.start()

    phone = "+79991234567"

    # --- Account State Tracking ---
    pulse.account_state(phone, AccountState.CONNECTING)
    pulse.account_state(phone, AccountState.MONITORING,
                        metadata={"channels": 47})

    # --- Metrics ---
    pulse.counter("messages_received", "account", phone,
                  tags={"channel": "tech_news", "type": "text"})
    pulse.gauge("active_listeners", "service", "my-service", value=3)
    pulse.histogram("query_latency_ms", "database", "clickhouse", value=45.2)

    # --- Structured Events ---
    pulse.event("session", phone, "health_check_ok",
                severity=Severity.INFO,
                message="Health check passed")

    pulse.event("session", phone, "reconnect_attempt",
                severity=Severity.WARNING,
                payload={"attempt": 2, "reason": "ConnectionReset"})

    # --- Spans (measure operations) ---
    async with pulse.span("process_messages", entity_id=phone) as span:
        span.set_tag("channel", "tech_news")
        await asyncio.sleep(0.1)  # simulate work
        span.set_metric("messages_processed", 42)

    # --- Decorators ---
    @pulse.track_latency("db_query", entity_type="database")
    async def run_query(sql: str):
        await asyncio.sleep(0.05)  # simulate query
        return [{"id": 1}]

    result = await run_query("SELECT 1")

    # --- Error States ---
    pulse.account_state(phone, AccountState.THROTTLED,
                        metadata={"flood_wait_seconds": 300})
    # ... after flood wait ...
    pulse.account_state(phone, AccountState.MONITORING)

    # --- Cleanup ---
    await pulse.stop()
    print("Done! Events sent to observability_events topic.")


if __name__ == "__main__":
    asyncio.run(main())
