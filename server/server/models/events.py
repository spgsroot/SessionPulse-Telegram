"""Pydantic models for API responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AccountMetrics(BaseModel):
    messages_1m: float = 0
    messages_5m: float = 0
    messages_15m: float = 0
    reactions_1m: float = 0
    errors_1h: int = 0
    active_channels: int = 0


class AccountStateResponse(BaseModel):
    phone: str
    state: str
    previous_state: str = ""
    state_since: str = ""
    error_message: str = ""
    last_event_at: str = ""
    metrics: AccountMetrics = AccountMetrics()


class AccountsListResponse(BaseModel):
    accounts: list[AccountStateResponse]
    summary: dict[str, Any]


class TimelineEvent(BaseModel):
    timestamp: str
    event_type: str
    event_name: str = ""
    severity: str = "info"
    message: str = ""
    payload: dict = {}
    entity_type: str = ""
    entity_id: str = ""


class TimelineResponse(BaseModel):
    events: list[TimelineEvent]
    total: int
    has_more: bool = False


class PipelineStageHealth(BaseModel):
    status: str = "unknown"
    throughput: float = 0
    latency_p50: float = 0
    latency_p95: float = 0
    error_rate: float = 0
    consumer_lag: int = 0


class PipelineHealthResponse(BaseModel):
    status: str = "unknown"
    stages: dict[str, PipelineStageHealth] = {}
    end_to_end: dict[str, float] = {}


class AlertResponse(BaseModel):
    alert_id: str
    rule_name: str
    severity: str
    status: str
    entity_type: str = ""
    entity_id: str = ""
    message: str = ""
    fired_at: str = ""
    resolved_at: str | None = None
    acknowledged_by: str = ""


class AlertsListResponse(BaseModel):
    alerts: list[AlertResponse]
    firing_count: int = 0
    total: int = 0


class SystemOverviewResponse(BaseModel):
    status: str = "operational"
    accounts: dict[str, Any] = {}
    pipeline: dict[str, Any] = {}
    alerts: dict[str, Any] = {}
