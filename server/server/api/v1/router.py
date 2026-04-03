"""API v1 router — all REST endpoints."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

logger = logging.getLogger("session_pulse.api")

router = APIRouter(prefix="/api/v1")

# Dependencies injected via app.state in main.py
_state_machine = None
_metrics = None
_alerts = None
_storage = None
_ws_manager = None


def init_router(state_machine, metrics, alerts, storage, ws_manager):
    global _state_machine, _metrics, _alerts, _storage, _ws_manager
    _state_machine = state_machine
    _metrics = metrics
    _alerts = alerts
    _storage = storage
    _ws_manager = ws_manager


# ── Accounts ──


@router.get("/accounts")
async def list_accounts():
    accounts = _state_machine.get_all_states()
    summary = _state_machine.get_summary()
    return {"accounts": accounts, "summary": summary}


@router.get("/accounts/{phone}/state")
async def get_account_state(phone: str):
    state = _state_machine.get_state(phone)
    if not state:
        return JSONResponse({"error": "Account not found"}, status_code=404)
    return state


@router.get("/accounts/{phone}/timeline")
async def get_account_timeline(
    phone: str,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
):
    events, total = await _storage.query_timeline(phone, limit, offset)
    return {
        "events": events,
        "total": total,
        "has_more": offset + limit < total,
    }


@router.get("/accounts/{phone}/metrics")
async def get_account_metrics(phone: str):
    account_metrics = _metrics.get_account_metrics(phone)
    state = _state_machine.get_state(phone)
    return {
        "phone": phone,
        "windows": account_metrics,
        "state": state,
    }


# ── Pipeline ──


@router.get("/pipeline/health")
async def get_pipeline_health():
    stages = {}
    for stage in ["capture", "produce", "consume", "store", "ml_score"]:
        key_throughput = f"pipeline:{stage}:throughput"
        key_latency = f"pipeline:{stage}:latency_ms"
        throughput = _metrics.get_sum(key_throughput, "1m")
        latency_p50 = _metrics.get_percentile(key_latency, "5m", 50)
        latency_p95 = _metrics.get_percentile(key_latency, "5m", 95)

        status = "healthy"
        if throughput == 0 and stage in ("consume", "store"):
            status = "unknown"

        stages[stage] = {
            "status": status,
            "throughput": round(throughput / 60, 1),
            "latency_p50": round(latency_p50, 1),
            "latency_p95": round(latency_p95, 1),
        }

    overall = "healthy"
    if any(s["status"] == "degraded" for s in stages.values()):
        overall = "degraded"

    return {"status": overall, "stages": stages}


# ── Alerts ──


@router.get("/alerts")
async def list_alerts(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    # Active (in-memory) alerts
    active = _alerts.get_active_alerts()

    # Historical alerts from storage
    historical = await _storage.query_alerts(status=status, limit=limit)

    # Merge: active alerts take precedence
    active_ids = {a["alert_id"] for a in active}
    merged = active + [h for h in historical if h["alert_id"] not in active_ids]

    firing_count = sum(1 for a in merged if a.get("status") == "firing")

    return {
        "alerts": merged[:limit],
        "firing_count": firing_count,
        "total": len(merged),
    }


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    for key, alert in _alerts._active.items():
        if alert.alert_id == alert_id:
            alert.status = "acknowledged"
            if _storage:
                await _storage.update_alert(alert)
            return {"status": "acknowledged", "alert_id": alert_id}
    return JSONResponse({"error": "Alert not found"}, status_code=404)


# ── Alert Rules CRUD ──


@router.get("/alerts/rules")
async def list_alert_rules():
    return {"rules": _alerts.get_rules()}


@router.post("/alerts/rules")
async def create_alert_rule(body: dict):
    if "name" not in body:
        return JSONResponse({"error": "name is required"}, status_code=400)
    rule = _alerts.add_rule(body)
    return {"status": "created", "rule": rule.name}


@router.put("/alerts/rules/{name}")
async def update_alert_rule(name: str, body: dict):
    rule = _alerts.update_rule(name, body)
    if not rule:
        return JSONResponse({"error": "Rule not found"}, status_code=404)
    return {"status": "updated", "rule": rule.name}


@router.delete("/alerts/rules/{name}")
async def delete_alert_rule(name: str):
    if _alerts.delete_rule(name):
        return {"status": "deleted", "rule": name}
    return JSONResponse({"error": "Rule not found"}, status_code=404)


# ── Anomaly Detection ──


@router.get("/anomalies")
async def get_anomalies():
    anomalies = _alerts.check_anomalies(_metrics)
    return {"anomalies": anomalies, "count": len(anomalies)}


# ── System ──


@router.get("/system/overview")
async def system_overview():
    summary = _state_machine.get_summary()
    active_alerts = _alerts.get_active_alerts()
    ch_healthy = await _storage.health_check()

    status = "operational"
    firing = [a for a in active_alerts if a["status"] == "firing"]
    if any(a["severity"] == "critical" for a in firing):
        status = "critical"
    elif firing:
        status = "degraded"

    return {
        "status": status,
        "accounts": summary,
        "pipeline": {"status": "healthy" if ch_healthy else "degraded"},
        "alerts": {
            "firing": len(firing),
            "total": len(active_alerts),
        },
        "clickhouse": "ok" if ch_healthy else "error",
    }


# ── Ingest (HTTP transport endpoint) ──


@router.post("/ingest")
async def ingest_events(body: dict):
    """Receive events from HTTP transport (alternative to Kafka)."""
    events = body.get("events", [])
    if not events:
        return {"status": "ok", "count": 0}

    # Import here to avoid circular deps
    from server.consumer.batch_processor import BatchProcessor

    # Get processor from app state (set in main.py)
    # For now, just store directly
    try:
        await _storage.insert_events(events)
        return {"status": "ok", "count": len(events)}
    except Exception as e:
        logger.error(f"Ingest error: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# ── WebSocket ──


@router.websocket("/ws/accounts")
async def ws_accounts(websocket: WebSocket):
    await _ws_manager.connect(websocket, "accounts")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await _ws_manager.disconnect(websocket, "accounts")


@router.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    await _ws_manager.connect(websocket, "alerts")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await _ws_manager.disconnect(websocket, "alerts")


@router.websocket("/ws/timeline/{phone}")
async def ws_timeline(websocket: WebSocket, phone: str):
    channel = f"timeline:{phone}"
    await _ws_manager.connect(websocket, channel)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await _ws_manager.disconnect(websocket, channel)
