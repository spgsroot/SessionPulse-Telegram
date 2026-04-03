"""
SessionPulse — Domain-aware observability for session-based distributed systems.

Usage:
    from session_pulse import SessionPulse, AccountState, Severity

    pulse = SessionPulse(
        service_name="backend",
        transport="kafka",
        kafka_bootstrap="redpanda:9092",
    )
    await pulse.start()

    pulse.account_state("+79991234567", AccountState.MONITORING)
    pulse.counter("messages_received", "account", "+79991234567")

    await pulse.stop()
"""

from .client import SessionPulse
from .core.states import AccountState, MetricType, Severity, SubscriptionStatus

__version__ = "0.1.0"

__all__ = [
    "AccountState",
    "MetricType",
    "SessionPulse",
    "Severity",
    "SubscriptionStatus",
]
