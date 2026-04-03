"""Observability event data structure (wire protocol v1)."""

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True)
class ObservabilityEvent:
    """Single observability event. Serialized to JSON for transport."""

    # Identity
    schema_version: int = 1
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # Source
    service_name: str = ""

    # Entity
    entity_type: str = ""
    entity_id: str = ""

    # Event classification
    event_type: str = ""
    event_name: str = ""
    severity: str = "info"

    # Data
    message: str = ""
    payload: str = "{}"

    # Metrics
    metric_name: str = ""
    metric_value: float = 0.0
    metric_type: str = ""
    tags: dict = field(default_factory=dict)

    # State
    previous_state: str = ""
    new_state: str = ""
    error_message: str = ""

    # Tracing
    trace_id: str = ""
    span_id: str = ""
    parent_span_id: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)
