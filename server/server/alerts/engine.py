"""Alert rule evaluation engine with YAML config, FOR-duration, pipeline metrics,
anomaly detection baseline, deduplication, and Telegram notification."""

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import yaml

logger = logging.getLogger("session_pulse.alerts")


@dataclass
class AlertRule:
    name: str
    description: str = ""
    condition_field: str = ""       # e.g. "state", "error_message"
    condition_op: str = "=="        # "==", "!=", "in", "contains", ">", "<", ">=", "<="
    condition_value: str = ""       # e.g. "error", "5000"
    entity_type: str = "account"    # "account", "pipeline", "metric"
    severity: str = "warning"       # "warning", "critical"
    cooldown_seconds: float = 300
    for_seconds: float = 0          # Alert only after condition persists for N seconds
    enabled: bool = True
    message_template: str = ""
    # For metric-based rules
    metric_name: str = ""           # e.g. "consumer_lag", "throughput"
    metric_window: str = "1m"       # "1m", "5m", "15m", "1h"


@dataclass
class Alert:
    alert_id: str
    rule_name: str
    severity: str
    status: str = "firing"          # "firing", "resolved", "acknowledged"
    entity_type: str = ""
    entity_id: str = ""
    message: str = ""
    fired_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    resolved_at: datetime | None = None
    acknowledged_by: str = ""


def load_rules_from_yaml(path: str) -> list[AlertRule]:
    """Load alert rules from a YAML configuration file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data or "rules" not in data:
            logger.warning(f"No rules found in {path}")
            return []
        rules = []
        for r in data["rules"]:
            rules.append(AlertRule(
                name=r["name"],
                description=r.get("description", ""),
                condition_field=r.get("condition_field", ""),
                condition_op=r.get("condition_op", "=="),
                condition_value=str(r.get("condition_value", "")),
                entity_type=r.get("entity_type", "account"),
                severity=r.get("severity", "warning"),
                cooldown_seconds=float(r.get("cooldown_seconds", 300)),
                for_seconds=float(r.get("for_seconds", 0)),
                enabled=r.get("enabled", True),
                message_template=r.get("message_template", ""),
                metric_name=r.get("metric_name", ""),
                metric_window=r.get("metric_window", "1m"),
            ))
        logger.info(f"Loaded {len(rules)} alert rules from {path}")
        return rules
    except FileNotFoundError:
        logger.warning(f"Alert rules file not found: {path}")
        return []
    except Exception as e:
        logger.error(f"Failed to load alert rules from {path}: {e}")
        return []


def save_rules_to_yaml(rules: list[AlertRule], path: str) -> bool:
    """Save alert rules back to YAML file."""
    try:
        data = {"rules": []}
        for r in rules:
            entry = {
                "name": r.name,
                "description": r.description,
                "condition_field": r.condition_field,
                "condition_op": r.condition_op,
                "condition_value": r.condition_value,
                "entity_type": r.entity_type,
                "severity": r.severity,
                "cooldown_seconds": r.cooldown_seconds,
                "for_seconds": r.for_seconds,
                "enabled": r.enabled,
                "message_template": r.message_template,
            }
            if r.metric_name:
                entry["metric_name"] = r.metric_name
                entry["metric_window"] = r.metric_window
            data["rules"].append(entry)

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        return True
    except Exception as e:
        logger.error(f"Failed to save alert rules to {path}: {e}")
        return False


# Default rules (used if no YAML file found)
DEFAULT_RULES = [
    AlertRule(
        name="account_offline",
        description="Account in error or recovering state for >5 min",
        condition_field="state",
        condition_op="in",
        condition_value="error,recovering",
        entity_type="account",
        severity="critical",
        cooldown_seconds=900,
        for_seconds=300,
        message_template="\U0001F534 Account {entity_id} is in {state} state. {error}",
    ),
    AlertRule(
        name="account_banned",
        description="Account banned by Telegram",
        condition_field="state",
        condition_op="==",
        condition_value="banned",
        entity_type="account",
        severity="critical",
        cooldown_seconds=0,
        message_template="\u26D4 Account {entity_id} BANNED by Telegram",
    ),
    AlertRule(
        name="account_throttled",
        description="Account received FloodWait",
        condition_field="state",
        condition_op="==",
        condition_value="throttled",
        entity_type="account",
        severity="warning",
        cooldown_seconds=0,
        message_template="\U0001F7E1 Account {entity_id} throttled (FloodWait)",
    ),
    AlertRule(
        name="account_auth_expired",
        description="Account session key expired",
        condition_field="error_message",
        condition_op="contains",
        condition_value="AuthKeyUnregistered",
        entity_type="account",
        severity="critical",
        cooldown_seconds=0,
        message_template="\U0001F511 Account {entity_id} session expired. Re-auth required.",
    ),
    AlertRule(
        name="high_consumer_lag",
        description="Kafka consumer falling behind",
        entity_type="metric",
        metric_name="pipeline:consume:consumer_lag",
        condition_op=">",
        condition_value="5000",
        metric_window="1m",
        severity="warning",
        cooldown_seconds=600,
        for_seconds=120,
        message_template="\U0001F4CA Consumer lag: {metric_value} events (threshold: 5000)",
    ),
    AlertRule(
        name="pipeline_error_spike",
        description="Pipeline error rate exceeds 5%",
        entity_type="metric",
        metric_name="pipeline:store:errors",
        condition_op=">",
        condition_value="0.05",
        metric_window="5m",
        severity="critical",
        cooldown_seconds=300,
        message_template="\U0001F6A8 Pipeline error rate: {metric_value:.2%}",
    ),
]


class AnomalyDetector:
    """Simple baseline anomaly detection using rolling averages.

    Maintains per-metric baselines (mean + stddev) and detects when current
    values deviate significantly (> threshold * stddev) from the baseline.
    """

    def __init__(self, window_size: int = 360, threshold: float = 3.0):
        self._baselines: dict[str, list[float]] = {}
        self._window_size = window_size
        self._threshold = threshold

    def add_sample(self, key: str, value: float) -> None:
        if key not in self._baselines:
            self._baselines[key] = []
        samples = self._baselines[key]
        samples.append(value)
        if len(samples) > self._window_size:
            samples.pop(0)

    def is_anomalous(self, key: str, value: float) -> tuple[bool, float, float]:
        """Returns (is_anomaly, mean, stddev)."""
        samples = self._baselines.get(key, [])
        if len(samples) < 30:
            return False, 0, 0

        mean = sum(samples) / len(samples)
        variance = sum((x - mean) ** 2 for x in samples) / len(samples)
        stddev = variance ** 0.5

        if stddev < 0.001:
            return False, mean, stddev

        deviation = abs(value - mean) / stddev
        return deviation > self._threshold, mean, stddev


class AlertEngine:
    def __init__(
        self,
        rules: list[AlertRule] | None = None,
        rules_path: str = "",
        storage=None,
        ws_manager=None,
        telegram_bot_token: str = "",
        telegram_chat_id: str = "",
    ):
        # Load rules: YAML file > provided rules > defaults
        if rules_path and os.path.exists(rules_path):
            self._rules = load_rules_from_yaml(rules_path)
        elif rules:
            self._rules = rules
        else:
            self._rules = list(DEFAULT_RULES)

        self._rules_path = rules_path
        self._storage = storage
        self._ws_manager = ws_manager
        self._bot_token = telegram_bot_token
        self._chat_id = telegram_chat_id
        self._active: dict[str, Alert] = {}
        self._cooldowns: dict[str, float] = {}
        self._pending_for: dict[str, float] = {}  # alert_key -> first_match_time
        self._session: aiohttp.ClientSession | None = None
        self._anomaly = AnomalyDetector()

    # ── Rule Management ──

    def get_rules(self) -> list[dict]:
        return [
            {
                "name": r.name,
                "description": r.description,
                "condition_field": r.condition_field,
                "condition_op": r.condition_op,
                "condition_value": r.condition_value,
                "entity_type": r.entity_type,
                "severity": r.severity,
                "cooldown_seconds": r.cooldown_seconds,
                "for_seconds": r.for_seconds,
                "enabled": r.enabled,
                "message_template": r.message_template,
                "metric_name": r.metric_name,
                "metric_window": r.metric_window,
            }
            for r in self._rules
        ]

    def add_rule(self, rule_data: dict) -> AlertRule:
        rule = AlertRule(
            name=rule_data["name"],
            description=rule_data.get("description", ""),
            condition_field=rule_data.get("condition_field", ""),
            condition_op=rule_data.get("condition_op", "=="),
            condition_value=str(rule_data.get("condition_value", "")),
            entity_type=rule_data.get("entity_type", "account"),
            severity=rule_data.get("severity", "warning"),
            cooldown_seconds=float(rule_data.get("cooldown_seconds", 300)),
            for_seconds=float(rule_data.get("for_seconds", 0)),
            enabled=rule_data.get("enabled", True),
            message_template=rule_data.get("message_template", ""),
            metric_name=rule_data.get("metric_name", ""),
            metric_window=rule_data.get("metric_window", "1m"),
        )
        # Replace if exists
        self._rules = [r for r in self._rules if r.name != rule.name]
        self._rules.append(rule)
        self._persist_rules()
        return rule

    def update_rule(self, name: str, updates: dict) -> AlertRule | None:
        for r in self._rules:
            if r.name == name:
                for key, val in updates.items():
                    if hasattr(r, key):
                        setattr(r, key, val)
                self._persist_rules()
                return r
        return None

    def delete_rule(self, name: str) -> bool:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        if len(self._rules) < before:
            # Clean up active alerts for this rule
            for key in list(self._active):
                if key.startswith(f"{name}:"):
                    del self._active[key]
            self._persist_rules()
            return True
        return False

    def _persist_rules(self) -> None:
        if self._rules_path:
            save_rules_to_yaml(self._rules, self._rules_path)

    # ── Evaluation ──

    async def evaluate(self, sm, metrics=None) -> None:
        now = time.time()

        for rule in self._rules:
            if not rule.enabled:
                continue

            try:
                if rule.entity_type == "account":
                    matches = self._eval_account_rule(rule, sm)
                elif rule.entity_type == "metric" and metrics:
                    matches = self._eval_metric_rule(rule, metrics)
                else:
                    matches = []

                matched_ids = set()
                for entity_id, context in matches:
                    alert_key = f"{rule.name}:{entity_id}"
                    matched_ids.add(entity_id)

                    # FOR-duration: only fire if condition persists
                    if rule.for_seconds > 0:
                        if alert_key not in self._pending_for:
                            self._pending_for[alert_key] = now
                            continue
                        elapsed = now - self._pending_for[alert_key]
                        if elapsed < rule.for_seconds:
                            continue

                    # Cooldown
                    last = self._cooldowns.get(alert_key, 0)
                    if rule.cooldown_seconds > 0 and (
                        now - last < rule.cooldown_seconds
                    ):
                        continue

                    if alert_key not in self._active:
                        try:
                            msg = rule.message_template.format(
                                entity_id=entity_id, **context
                            )
                        except (KeyError, ValueError):
                            msg = f"Alert {rule.name}: {entity_id}"

                        alert = Alert(
                            alert_id=uuid.uuid4().hex[:8],
                            rule_name=rule.name,
                            severity=rule.severity,
                            entity_type=rule.entity_type,
                            entity_id=entity_id,
                            message=msg,
                        )
                        self._active[alert_key] = alert
                        self._cooldowns[alert_key] = now

                        if self._storage:
                            try:
                                await self._storage.insert_alert(alert)
                            except Exception as e:
                                logger.error(f"Failed to store alert: {e}")

                        await self._notify(alert)
                        await self._ws_broadcast(alert, "alert_fired")

                # Clear pending_for for non-matching
                for key in list(self._pending_for):
                    if key.startswith(f"{rule.name}:"):
                        eid = key.split(":", 1)[1]
                        if eid not in matched_ids:
                            del self._pending_for[key]

                # Auto-resolve
                for alert_key, alert in list(self._active.items()):
                    if alert.rule_name == rule.name:
                        eid = alert_key.split(":", 1)[1]
                        if eid not in matched_ids:
                            alert.status = "resolved"
                            alert.resolved_at = datetime.now(timezone.utc)
                            if self._storage:
                                try:
                                    await self._storage.update_alert(alert)
                                except Exception:
                                    pass
                            await self._ws_broadcast(alert, "alert_resolved")
                            del self._active[alert_key]

            except Exception as e:
                logger.error(f"Alert rule {rule.name} error: {e}")

    def _eval_account_rule(self, rule, sm) -> list[tuple[str, dict]]:
        matches = []
        values = (
            set(rule.condition_value.split(","))
            if rule.condition_op == "in"
            else {rule.condition_value}
        )

        for phone, entry in sm._states.items():
            field_val = getattr(entry, rule.condition_field, "")
            match = self._check_condition(rule.condition_op, str(field_val), rule.condition_value, values)
            if match:
                matches.append((
                    phone,
                    {
                        "state": entry.state,
                        "error": entry.error_message,
                        "phone": phone,
                    },
                ))

        return matches

    def _eval_metric_rule(self, rule, metrics) -> list[tuple[str, dict]]:
        """Evaluate metric-based rules against rolling window data."""
        matches = []
        key = rule.metric_name
        if not key:
            return matches

        value = metrics.get_sum(key, rule.metric_window)

        # Feed anomaly detector
        self._anomaly.add_sample(key, value)

        threshold = float(rule.condition_value) if rule.condition_value else 0
        values_set = set()
        match = self._check_condition(
            rule.condition_op, str(value), rule.condition_value, values_set
        )

        if match:
            matches.append((
                key,
                {
                    "metric_name": key,
                    "metric_value": value,
                    "threshold": threshold,
                    "window": rule.metric_window,
                },
            ))

        return matches

    @staticmethod
    def _check_condition(op: str, field_val: str, condition_val: str,
                         values_set: set[str]) -> bool:
        if op == "==":
            return field_val == condition_val
        elif op == "!=":
            return field_val != condition_val
        elif op == "in":
            return field_val in values_set
        elif op == "contains":
            return condition_val in field_val
        elif op in (">", "<", ">=", "<="):
            try:
                fv = float(field_val)
                cv = float(condition_val)
                if op == ">": return fv > cv
                if op == "<": return fv < cv
                if op == ">=": return fv >= cv
                if op == "<=": return fv <= cv
            except (ValueError, TypeError):
                return False
        return False

    # ── Anomaly Detection ──

    def check_anomalies(self, metrics) -> list[dict]:
        """Check all tracked metrics for anomalies. Returns detected anomalies."""
        anomalies = []
        for key in list(self._anomaly._baselines.keys()):
            value = metrics.get_sum(key, "5m")
            is_anom, mean, stddev = self._anomaly.is_anomalous(key, value)
            if is_anom:
                anomalies.append({
                    "metric": key,
                    "current_value": value,
                    "baseline_mean": round(mean, 2),
                    "baseline_stddev": round(stddev, 2),
                    "deviation": round(abs(value - mean) / max(stddev, 0.001), 1),
                })
        return anomalies

    # ── Notification ──

    async def _notify(self, alert: Alert) -> None:
        if not self._bot_token or not self._chat_id:
            return

        try:
            if not self._session or self._session.closed:
                self._session = aiohttp.ClientSession()

            severity_icon = {
                "critical": "\U0001F6A8",
                "warning": "\u26A0\uFE0F",
            }.get(alert.severity, "\u2139\uFE0F")

            url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
            text = (
                f"{severity_icon} <b>[SessionPulse | {alert.severity.upper()}]</b>\n\n"
                f"{alert.message}\n\n"
                f"<i>Rule: {alert.rule_name} | ID: {alert.alert_id}</i>"
            )
            await self._session.post(
                url,
                json={
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            )
        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")

    async def _ws_broadcast(self, alert: Alert, event_type: str) -> None:
        if not self._ws_manager:
            return
        try:
            await self._ws_manager.broadcast("alerts", {
                "type": event_type,
                "alert_id": alert.alert_id,
                "rule_name": alert.rule_name,
                "severity": alert.severity,
                "status": alert.status,
                "entity_type": alert.entity_type,
                "entity_id": alert.entity_id,
                "message": alert.message,
                "fired_at": alert.fired_at.isoformat(),
                "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            })
        except Exception as e:
            logger.debug(f"WS alert broadcast error: {e}")

    # ── Evaluation Loop ──

    async def evaluation_loop(self, sm, metrics=None, interval: float = 10.0):
        while True:
            await asyncio.sleep(interval)
            await self.evaluate(sm, metrics)

    # ── Getters ──

    def get_active_alerts(self) -> list[dict]:
        return [
            {
                "alert_id": a.alert_id,
                "rule_name": a.rule_name,
                "severity": a.severity,
                "status": a.status,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "message": a.message,
                "fired_at": a.fired_at.isoformat(),
            }
            for a in self._active.values()
        ]

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
