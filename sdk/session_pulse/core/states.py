"""State enums for SessionPulse observability."""

from enum import Enum


class AccountState(str, Enum):
    CREATED = "created"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    MONITORING = "monitoring"
    THROTTLED = "throttled"
    RECOVERING = "recovering"
    STOPPED = "stopped"
    ERROR = "error"
    BANNED = "banned"
    DELETED = "deleted"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    SILENT = "silent"
    ACCESS_DENIED = "access_denied"
    BANNED = "banned"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
