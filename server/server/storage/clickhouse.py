"""ClickHouse storage implementation."""

import asyncio
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import clickhouse_connect

logger = logging.getLogger("session_pulse.storage")


class ClickHouseStorage:
    def __init__(self, host: str, port: int, username: str, password: str,
                 database: str, pool_size: int = 10):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._database = database
        self._executor = ThreadPoolExecutor(max_workers=pool_size)
        self._pool: list = []
        self._pool_lock = threading.Lock()
        self._pool_size = pool_size

    def _get_client(self):
        with self._pool_lock:
            if self._pool:
                return self._pool.pop()
        return clickhouse_connect.get_client(
            host=self._host,
            port=self._port,
            username=self._username,
            password=self._password,
            database=self._database,
        )

    def _release_client(self, client):
        with self._pool_lock:
            if len(self._pool) < self._pool_size:
                self._pool.append(client)
            else:
                client.close()

    async def _run(self, func, *args):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, func, *args)

    async def init_tables(self) -> None:
        def _create():
            client = self._get_client()
            try:
                client.command(
                    f"CREATE DATABASE IF NOT EXISTS {self._database}"
                )

                client.command(f"""
                    CREATE TABLE IF NOT EXISTS {self._database}.events (
                        event_id String DEFAULT generateUUIDv4(),
                        timestamp DateTime64(3, 'UTC'),
                        service_name LowCardinality(String),
                        entity_type LowCardinality(String),
                        entity_id String,
                        event_type LowCardinality(String),
                        event_name String DEFAULT '',
                        severity LowCardinality(String) DEFAULT 'info',
                        message String DEFAULT '',
                        payload String DEFAULT '{{}}',
                        metric_name String DEFAULT '',
                        metric_value Float64 DEFAULT 0,
                        metric_type LowCardinality(String) DEFAULT '',
                        tags Map(String, String),
                        previous_state LowCardinality(String) DEFAULT '',
                        new_state LowCardinality(String) DEFAULT '',
                        error_message String DEFAULT '',
                        trace_id String DEFAULT '',
                        span_id String DEFAULT '',
                        parent_span_id String DEFAULT '',
                        duration_ms Float64 DEFAULT 0,
                        schema_version UInt8 DEFAULT 1
                    ) ENGINE = MergeTree()
                    PARTITION BY toYYYYMMDD(timestamp)
                    ORDER BY (entity_type, entity_id, timestamp)
                    TTL toDateTime(timestamp) + INTERVAL 30 DAY
                    SETTINGS index_granularity = 8192
                """)

                client.command(f"""
                    CREATE TABLE IF NOT EXISTS {self._database}.account_states (
                        phone String,
                        state LowCardinality(String),
                        previous_state LowCardinality(String) DEFAULT '',
                        state_since DateTime64(3, 'UTC'),
                        error_message String DEFAULT '',
                        metadata String DEFAULT '{{}}',
                        last_event_at DateTime64(3, 'UTC'),
                        updated_at DateTime64(3, 'UTC')
                    ) ENGINE = ReplacingMergeTree(updated_at)
                    ORDER BY (phone)
                """)

                client.command(f"""
                    CREATE TABLE IF NOT EXISTS {self._database}.subscription_health (
                        phone String,
                        chat_id Int64,
                        chat_title String DEFAULT '',
                        status LowCardinality(String) DEFAULT 'unknown',
                        messages_1h Float64 DEFAULT 0,
                        last_message_at DateTime64(3, 'UTC'),
                        last_error String DEFAULT '',
                        last_error_at Nullable(DateTime64(3, 'UTC')),
                        updated_at DateTime64(3, 'UTC')
                    ) ENGINE = ReplacingMergeTree(updated_at)
                    ORDER BY (phone, chat_id)
                """)

                client.command(f"""
                    CREATE TABLE IF NOT EXISTS {self._database}.alert_history (
                        alert_id String,
                        rule_name String,
                        severity LowCardinality(String),
                        status LowCardinality(String),
                        entity_type String DEFAULT '',
                        entity_id String DEFAULT '',
                        message String DEFAULT '',
                        payload String DEFAULT '{{}}',
                        fired_at DateTime64(3, 'UTC'),
                        resolved_at Nullable(DateTime64(3, 'UTC')),
                        acknowledged_by String DEFAULT '',
                        acknowledged_at Nullable(DateTime64(3, 'UTC')),
                        updated_at DateTime64(3, 'UTC')
                    ) ENGINE = ReplacingMergeTree(updated_at)
                    ORDER BY (alert_id)
                """)

                logger.info("ClickHouse tables created successfully")
            finally:
                self._release_client(client)

        await self._run(_create)

    async def insert_events(self, events: list[dict]) -> None:
        if not events:
            return

        def _insert():
            client = self._get_client()
            try:
                rows = []
                for e in events:
                    ts = e.get("timestamp", "")
                    if isinstance(ts, str):
                        try:
                            ts = datetime.fromisoformat(
                                ts.replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            ts = datetime.now(timezone.utc)
                    elif not isinstance(ts, datetime):
                        ts = datetime.now(timezone.utc)

                    tags = e.get("tags", {})
                    if not isinstance(tags, dict):
                        tags = {}

                    rows.append([
                        e.get("event_id", ""),
                        ts,
                        e.get("service_name", ""),
                        e.get("entity_type", ""),
                        e.get("entity_id", ""),
                        e.get("event_type", ""),
                        e.get("event_name", ""),
                        e.get("severity", "info"),
                        e.get("message", ""),
                        e.get("payload", "{}"),
                        e.get("metric_name", ""),
                        float(e.get("metric_value", 0)),
                        e.get("metric_type", ""),
                        tags,
                        e.get("previous_state", ""),
                        e.get("new_state", ""),
                        e.get("error_message", ""),
                        e.get("trace_id", ""),
                        e.get("span_id", ""),
                        e.get("parent_span_id", ""),
                        float(e.get("duration_ms", 0)),
                        int(e.get("schema_version", 1)),
                    ])

                columns = [
                    "event_id", "timestamp", "service_name",
                    "entity_type", "entity_id", "event_type",
                    "event_name", "severity", "message", "payload",
                    "metric_name", "metric_value", "metric_type", "tags",
                    "previous_state", "new_state", "error_message",
                    "trace_id", "span_id", "parent_span_id",
                    "duration_ms", "schema_version",
                ]
                client.insert(
                    f"{self._database}.events",
                    rows,
                    column_names=columns,
                )
            finally:
                self._release_client(client)

        await self._run(_insert)

    async def get_all_account_states(self) -> list[dict]:
        def _query():
            client = self._get_client()
            try:
                result = client.query(
                    f"SELECT phone, state, previous_state, state_since, "
                    f"error_message, metadata, last_event_at "
                    f"FROM {self._database}.account_states FINAL"
                )
                rows = []
                for row in result.result_rows:
                    rows.append({
                        "phone": row[0],
                        "state": row[1],
                        "previous_state": row[2],
                        "state_since": row[3],
                        "error_message": row[4],
                        "metadata": row[5],
                        "last_event_at": row[6],
                    })
                return rows
            finally:
                self._release_client(client)

        return await self._run(_query)

    async def upsert_account_states(self, entries: list) -> None:
        if not entries:
            return

        def _upsert():
            client = self._get_client()
            try:
                now = datetime.now(timezone.utc)
                rows = []
                for e in entries:
                    state_since = e.state_since
                    if isinstance(state_since, str):
                        try:
                            state_since = datetime.fromisoformat(state_since)
                        except (ValueError, TypeError):
                            state_since = now
                    last_event = getattr(e, "last_event_at", now)
                    if isinstance(last_event, str):
                        try:
                            last_event = datetime.fromisoformat(last_event)
                        except (ValueError, TypeError):
                            last_event = now

                    rows.append([
                        e.phone,
                        e.state,
                        e.previous_state,
                        state_since,
                        e.error_message,
                        json.dumps(e.metadata) if isinstance(e.metadata, dict) else str(e.metadata),
                        last_event,
                        now,
                    ])
                client.insert(
                    f"{self._database}.account_states",
                    rows,
                    column_names=[
                        "phone", "state", "previous_state", "state_since",
                        "error_message", "metadata", "last_event_at",
                        "updated_at",
                    ],
                )
            finally:
                self._release_client(client)

        await self._run(_upsert)

    async def query_timeline(
        self, entity_id: str, limit: int = 100, offset: int = 0
    ) -> tuple[list[dict], int]:
        def _query():
            client = self._get_client()
            try:
                count_result = client.query(
                    f"SELECT count() FROM {self._database}.events "
                    f"WHERE entity_id = %(eid)s",
                    parameters={"eid": entity_id},
                )
                total = count_result.result_rows[0][0] if count_result.result_rows else 0

                result = client.query(
                    f"SELECT timestamp, event_type, event_name, severity, "
                    f"message, payload, entity_type, entity_id "
                    f"FROM {self._database}.events "
                    f"WHERE entity_id = %(eid)s "
                    f"ORDER BY timestamp DESC "
                    f"LIMIT %(limit)s OFFSET %(offset)s",
                    parameters={
                        "eid": entity_id,
                        "limit": limit,
                        "offset": offset,
                    },
                )
                events = []
                for row in result.result_rows:
                    events.append({
                        "timestamp": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                        "event_type": row[1],
                        "event_name": row[2],
                        "severity": row[3],
                        "message": row[4],
                        "payload": row[5],
                        "entity_type": row[6],
                        "entity_id": row[7],
                    })
                return events, total
            finally:
                self._release_client(client)

        return await self._run(_query)

    async def insert_alert(self, alert) -> None:
        def _insert():
            client = self._get_client()
            try:
                now = datetime.now(timezone.utc)
                client.insert(
                    f"{self._database}.alert_history",
                    [[
                        alert.alert_id,
                        alert.rule_name,
                        alert.severity,
                        alert.status,
                        alert.entity_type,
                        alert.entity_id,
                        alert.message,
                        "{}",
                        alert.fired_at,
                        None,
                        "",
                        None,
                        now,
                    ]],
                    column_names=[
                        "alert_id", "rule_name", "severity", "status",
                        "entity_type", "entity_id", "message", "payload",
                        "fired_at", "resolved_at", "acknowledged_by",
                        "acknowledged_at", "updated_at",
                    ],
                )
            finally:
                self._release_client(client)

        await self._run(_insert)

    async def update_alert(self, alert) -> None:
        await self.insert_alert(alert)  # ReplacingMergeTree handles upsert

    async def query_alerts(
        self, status: str | None = None, limit: int = 50
    ) -> list[dict]:
        def _query():
            client = self._get_client()
            try:
                where = ""
                params = {"limit": limit}
                if status:
                    where = "WHERE status = %(status)s"
                    params["status"] = status

                result = client.query(
                    f"SELECT alert_id, rule_name, severity, status, "
                    f"entity_type, entity_id, message, fired_at, "
                    f"resolved_at, acknowledged_by "
                    f"FROM {self._database}.alert_history FINAL "
                    f"{where} "
                    f"ORDER BY fired_at DESC LIMIT %(limit)s",
                    parameters=params,
                )
                alerts = []
                for row in result.result_rows:
                    alerts.append({
                        "alert_id": row[0],
                        "rule_name": row[1],
                        "severity": row[2],
                        "status": row[3],
                        "entity_type": row[4],
                        "entity_id": row[5],
                        "message": row[6],
                        "fired_at": row[7].isoformat() if hasattr(row[7], "isoformat") else str(row[7]),
                        "resolved_at": row[8].isoformat() if row[8] and hasattr(row[8], "isoformat") else None,
                        "acknowledged_by": row[9],
                    })
                return alerts
            finally:
                self._release_client(client)

        return await self._run(_query)

    async def health_check(self) -> bool:
        def _check():
            client = self._get_client()
            try:
                client.query("SELECT 1")
                return True
            except Exception:
                return False
            finally:
                self._release_client(client)

        try:
            return await self._run(_check)
        except Exception:
            return False

    async def close(self) -> None:
        with self._pool_lock:
            for client in self._pool:
                try:
                    client.close()
                except Exception:
                    pass
            self._pool.clear()
        self._executor.shutdown(wait=False)
