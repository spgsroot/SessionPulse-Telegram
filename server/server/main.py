"""SessionPulse Server — FastAPI application entry point."""

import asyncio
import contextlib
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from .alerts.engine import AlertEngine
from .api.v1.router import init_router, router as v1_router
from .api.websocket.manager import WebSocketManager
from .config import load_config
from .consumer.batch_processor import BatchProcessor
from .consumer.kafka_consumer import EventConsumer
from .metrics.windows import RollingWindowCalculator
from .state.machine import AccountStateMachine
from .state.timeout_monitor import TimeoutMonitor
from .storage.clickhouse import ClickHouseStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("session_pulse")

# Global references for lifecycle management
_consumer: EventConsumer | None = None
_consumer_task: asyncio.Task | None = None
_bg_tasks: list[asyncio.Task] = []
_storage: ClickHouseStorage | None = None
_state_machine: AccountStateMachine | None = None
_alert_engine: AlertEngine | None = None
_ws_manager: WebSocketManager | None = None
_timeout_monitor: TimeoutMonitor | None = None


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    global _consumer, _consumer_task, _bg_tasks, _storage
    global _state_machine, _alert_engine, _ws_manager, _timeout_monitor

    config = load_config()

    # 1. Storage
    _storage = ClickHouseStorage(
        host=config.storage.host,
        port=config.storage.port,
        username=config.storage.username,
        password=config.storage.password,
        database=config.storage.database,
        pool_size=config.storage.pool_size,
    )
    await _storage.init_tables()
    logger.info("ClickHouse storage initialized")

    # 2. State machine
    _state_machine = AccountStateMachine(_storage)
    count = await _state_machine.load_from_storage()
    logger.info(f"State machine loaded ({count} accounts)")

    # 3. Metrics
    metrics = RollingWindowCalculator()

    # 4. WebSocket manager
    _ws_manager = WebSocketManager()
    _state_machine.set_ws_manager(_ws_manager)

    # 5. Alert engine (loads rules from YAML if available)
    rules_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config", "alert_rules.yaml"
    )
    _alert_engine = AlertEngine(
        rules_path=rules_path,
        storage=_storage,
        ws_manager=_ws_manager,
        telegram_bot_token=config.alerts.telegram_bot_token,
        telegram_chat_id=config.alerts.telegram_chat_id,
    )

    # 6. Initialize API router dependencies
    init_router(_state_machine, metrics, _alert_engine, _storage, _ws_manager)

    # 7. Batch processor
    processor = BatchProcessor(
        _state_machine, metrics, _alert_engine, _ws_manager, _storage
    )

    # 8. Kafka consumer
    _consumer = EventConsumer(
        bootstrap=config.consumer.bootstrap,
        topic=config.consumer.topic,
        group_id=config.consumer.group_id,
        processor=processor,
    )
    _consumer_task = asyncio.create_task(_consumer.run())

    # 9. Background tasks
    _timeout_monitor = TimeoutMonitor(
        _state_machine,
        heartbeat_timeout=config.state.heartbeat_timeout_sec,
        max_recover_time=config.state.max_recover_time_sec,
        check_interval=config.state.timeout_check_interval_sec,
    )

    _bg_tasks = [
        asyncio.create_task(
            _state_machine.flush_loop(config.state.flush_interval_sec)
        ),
        asyncio.create_task(_timeout_monitor.run()),
        asyncio.create_task(
            _alert_engine.evaluation_loop(
                _state_machine, metrics, config.alerts.evaluation_interval_sec
            )
        ),
        asyncio.create_task(_metrics_cleanup_loop(metrics)),
    ]

    logger.info("SessionPulse server started")

    yield

    # Shutdown
    logger.info("Shutting down...")

    if _consumer:
        await _consumer.stop()
    if _consumer_task:
        _consumer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _consumer_task

    for task in _bg_tasks:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    if _state_machine:
        await _state_machine._flush_dirty()
    if _alert_engine:
        await _alert_engine.close()
    if _storage:
        await _storage.close()

    logger.info("SessionPulse server stopped")


async def _metrics_cleanup_loop(metrics: RollingWindowCalculator):
    while True:
        await asyncio.sleep(60)
        removed = metrics.cleanup()
        if removed > 0:
            logger.debug(f"Cleaned up {removed} expired metric samples")


# ── App ──

app = FastAPI(
    title="SessionPulse",
    description="Domain-aware observability for session-based systems",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(v1_router)


# ── Health endpoints ──


@app.get("/healthz")
async def healthz():
    return JSONResponse({"status": "ok"})


@app.get("/readyz")
async def readyz():
    checks = {}
    if _storage:
        checks["clickhouse"] = "ok" if await _storage.health_check() else "error"
    else:
        checks["clickhouse"] = "not_initialized"

    status = "ready" if all(v == "ok" for v in checks.values()) else "not_ready"
    code = 200 if status == "ready" else 503
    return JSONResponse({"status": status, "checks": checks}, status_code=code)


@app.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics endpoint."""
    lines = []

    if _state_machine:
        summary = _state_machine.get_summary()
        lines.append(
            "# HELP session_pulse_accounts_total Total monitored accounts"
        )
        lines.append("# TYPE session_pulse_accounts_total gauge")
        for state, count in summary.get("by_state", {}).items():
            lines.append(
                f'session_pulse_accounts_total{{state="{state}"}} {count}'
            )

    if _alert_engine:
        active = _alert_engine.get_active_alerts()
        firing = sum(1 for a in active if a["status"] == "firing")
        lines.append("# HELP session_pulse_alerts_firing Active firing alerts")
        lines.append("# TYPE session_pulse_alerts_firing gauge")
        lines.append(f"session_pulse_alerts_firing {firing}")

    if _ws_manager:
        lines.append(
            "# HELP session_pulse_ws_connections Active WebSocket connections"
        )
        lines.append("# TYPE session_pulse_ws_connections gauge")
        lines.append(
            f"session_pulse_ws_connections {_ws_manager.connection_count}"
        )

    return PlainTextResponse("\n".join(lines) + "\n")
