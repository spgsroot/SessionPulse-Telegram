# SessionPulse SDK

Domain-aware observability for session-based distributed systems.

Zero-dependency core. Fire-and-forget. Non-blocking. Async-native.

## Installation

```bash
pip install session-pulse              # core only (noop transport)
pip install session-pulse[kafka]       # with Kafka/Redpanda transport
pip install session-pulse[http]        # with HTTP push transport
pip install session-pulse[all]         # kafka + http
```

## Quick Start

```python
from session_pulse import SessionPulse, AccountState, Severity

pulse = SessionPulse(
    service_name="my-service",
    transport="kafka",                    # "kafka" | "http" | "noop"
    kafka_bootstrap="redpanda:9092",
    kafka_topic="observability_events",
)

await pulse.start()

# Track account lifecycle
pulse.account_state("+79991234567", AccountState.MONITORING)
pulse.account_state("+79991234567", AccountState.THROTTLED,
                    metadata={"flood_wait_seconds": 300})

# Metrics
pulse.counter("messages_received", "account", "+79991234567",
              tags={"channel": "tech_news"})
pulse.gauge("active_listeners", "service", "backend", value=15)
pulse.histogram("query_latency_ms", "database", "clickhouse", value=45.2)

# Structured events
pulse.event("session", "+79991234567", "reconnect_attempt",
            severity=Severity.WARNING,
            payload={"attempt": 3, "reason": "ConnectionReset"})

await pulse.stop()
```

## Decorators

```python
@pulse.track_latency("db_query")
async def execute_query(query: str):
    ...

@pulse.track_session(phone_param="phone")
async def get_client(phone: str):
    ...
```

## Context Manager (Spans)

```python
async with pulse.span("parse_channel", entity_id=str(chat_id)) as span:
    span.set_tag("channel_name", "tech_news")
    messages = await parse_messages(...)
    span.set_metric("messages_parsed", len(messages))
```

## Framework Integrations

### Quart

```python
from session_pulse.integrations.quart import instrument_quart
instrument_quart(app, pulse)
# Auto-tracks: request latency, status codes, errors per endpoint
```

### Aiogram 3.x

```python
from session_pulse.integrations.aiogram import instrument_aiogram
instrument_aiogram(dp, pulse)
# Auto-tracks: handler execution time, command usage, errors
```

## Account States

```
CREATED -> CONNECTING -> CONNECTED -> MONITORING -> STOPPED
                                   -> THROTTLED  -> MONITORING
                                   -> RECOVERING -> MONITORING
                                   -> ERROR      -> CONNECTING
                                   -> BANNED     (terminal)
```

## Architecture

```
emit() -> BatchBuffer (in-memory, 1000 events / 5s)
              |
              v  (background flush)
        CircuitBreaker (5 failures -> OPEN, 60s recovery)
              |
              v
         Transport (Kafka / HTTP / Noop)
              |
              v (on failure)
         RingBuffer (10K events, retry every 30s)
```

- `emit()` is O(1), never blocks, never raises exceptions
- Flush runs in a background asyncio task
- Circuit breaker prevents cascade failures when transport is down
- Ring buffer prevents data loss during brief outages

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `service_name` | required | Service identifier in events |
| `transport` | `"noop"` | `"kafka"`, `"http"`, `"noop"` |
| `kafka_bootstrap` | `""` | Kafka bootstrap servers |
| `kafka_topic` | `"observability_events"` | Kafka topic name |
| `http_endpoint` | `""` | HTTP push URL |
| `buffer_size` | `1000` | Events before flush trigger |
| `flush_interval_ms` | `5000` | Max time before flush |
| `ring_buffer_size` | `10000` | Overflow buffer capacity |
| `sampling_rate` | `1.0` | 1.0 = all events, 0.1 = 10% |

## Security

The SDK automatically strips sensitive fields from payloads:
`session_string`, `api_hash`, `password`, `secret_key`, `token`

## License

MIT
