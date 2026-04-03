# SessionPulse Server

Aggregator and API server for SessionPulse observability system.

Consumes events from Kafka, maintains account state machines, evaluates alert rules, serves REST API and WebSocket for real-time dashboards.

## Quick Start

```bash
# With Docker (recommended)
docker compose up session-pulse

# Or standalone
pip install -r requirements.txt
uvicorn server.main:app --host 0.0.0.0 --port 8500
```

## Configuration

All configuration via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CLICKHOUSE_HOST` | `clickhouse` | ClickHouse server host |
| `CLICKHOUSE_PORT` | `9000` | ClickHouse native TCP port |
| `CLICKHOUSE_USER` | `default` | ClickHouse username |
| `CLICKHOUSE_PASSWORD` | `""` | ClickHouse password |
| `CLICKHOUSE_DATABASE` | `observability` | Database name |
| `KAFKA_BOOTSTRAP` | `redpanda:29092` | Kafka bootstrap servers |
| `KAFKA_TOPIC` | `observability_events` | Topic to consume |
| `TELEGRAM_BOT_TOKEN` | `""` | Bot token for alert notifications |
| `TELEGRAM_CHAT_ID` | `""` | Chat ID for alert notifications |
| `HEARTBEAT_TIMEOUT_SEC` | `60` | Seconds without heartbeat before RECOVERING |
| `MAX_RECOVER_TIME_SEC` | `3600` | Max recovery time before ERROR |

## API Endpoints

### Accounts

```
GET  /api/v1/accounts                     All accounts with state and metrics
GET  /api/v1/accounts/{phone}/state       Single account state
GET  /api/v1/accounts/{phone}/timeline    Event timeline (paginated)
GET  /api/v1/accounts/{phone}/metrics     Rolling window metrics
```

### Pipeline

```
GET  /api/v1/pipeline/health              Pipeline health by stage
```

### Alerts

```
GET  /api/v1/alerts                       Active + historical alerts
POST /api/v1/alerts/{id}/acknowledge      Acknowledge alert
GET  /api/v1/alerts/rules                 List alert rules
POST /api/v1/alerts/rules                 Create rule
PUT  /api/v1/alerts/rules/{name}          Update rule
DELETE /api/v1/alerts/rules/{name}        Delete rule
```

### Anomaly Detection

```
GET  /api/v1/anomalies                    Detected anomalies (baseline)
```

### System

```
GET  /api/v1/system/overview              System health summary
POST /api/v1/ingest                       HTTP event ingestion
GET  /healthz                             Liveness probe
GET  /readyz                              Readiness probe (checks ClickHouse)
GET  /metrics                             Prometheus-compatible metrics
```

### WebSocket

```
WS   /api/v1/ws/accounts                  Real-time account state changes
WS   /api/v1/ws/alerts                    Real-time alert notifications
WS   /api/v1/ws/timeline/{phone}          Real-time events for account
```

## Account State Machine

```
CREATED -> CONNECTING -> CONNECTED -> MONITORING
                                       |  |  |
                              THROTTLED-+  |  +--> RECOVERING --> MONITORING
                                           |                 \-> ERROR
                              STOPPED <----+
                              ERROR -----> CONNECTING
                              BANNED       (terminal)
```

Timeout transitions (automatic):
- MONITORING + no heartbeat > 60s -> RECOVERING
- RECOVERING > 1 hour -> ERROR
- THROTTLED past flood_wait -> MONITORING

## Alert Rules

Rules defined in `config/alert_rules.yaml`:

```yaml
rules:
  - name: account_offline
    condition_field: state
    condition_op: "in"
    condition_value: "error,recovering"
    entity_type: account
    severity: critical
    for_seconds: 300        # fire only after 5 min
    cooldown_seconds: 900
    message_template: "Account {entity_id} offline"
```

Supported operators: `==`, `!=`, `in`, `contains`, `>`, `<`, `>=`, `<=`

## Architecture

```
Kafka Topic                 ClickHouse (observability DB)
  |                                ^
  v                                |
EventConsumer --> BatchProcessor --+--> StateMachine
                      |                    |
                      +--> RollingWindows   +--> WebSocket
                      |                    |
                      +--> AlertEngine ----+--> Telegram
```

## License

MIT
