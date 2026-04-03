"""Server configuration from environment variables and YAML."""

import os
from dataclasses import dataclass, field


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8500


@dataclass
class StorageConfig:
    type: str = "clickhouse"
    host: str = "clickhouse"
    port: int = 8123
    username: str = "default"
    password: str = ""
    database: str = "observability"
    pool_size: int = 10


@dataclass
class ConsumerConfig:
    bootstrap: str = "redpanda:29092"
    topic: str = "observability_events"
    group_id: str = "session_pulse_aggregator_v1"


@dataclass
class StateConfig:
    heartbeat_timeout_sec: float = 60.0
    max_recover_time_sec: float = 3600.0
    timeout_check_interval_sec: float = 10.0
    flush_interval_sec: float = 10.0


@dataclass
class AlertConfig:
    evaluation_interval_sec: float = 10.0
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""


@dataclass
class Config:
    server: ServerConfig = field(default_factory=ServerConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    consumer: ConsumerConfig = field(default_factory=ConsumerConfig)
    state: StateConfig = field(default_factory=StateConfig)
    alerts: AlertConfig = field(default_factory=AlertConfig)


def load_config() -> Config:
    return Config(
        server=ServerConfig(
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8500")),
        ),
        storage=StorageConfig(
            host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
            port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
            username=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", ""),
            database=os.getenv("PULSE_CLICKHOUSE_DATABASE", "observability"),
            pool_size=int(os.getenv("CLICKHOUSE_POOL_SIZE", "10")),
        ),
        consumer=ConsumerConfig(
            bootstrap=os.getenv("KAFKA_BOOTSTRAP", "redpanda:29092"),
            topic=os.getenv("PULSE_KAFKA_TOPIC", "observability_events"),
            group_id=os.getenv(
                "KAFKA_GROUP_ID", "session_pulse_aggregator_v1"
            ),
        ),
        state=StateConfig(
            heartbeat_timeout_sec=float(
                os.getenv("HEARTBEAT_TIMEOUT_SEC", "60")
            ),
            max_recover_time_sec=float(
                os.getenv("MAX_RECOVER_TIME_SEC", "3600")
            ),
        ),
        alerts=AlertConfig(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        ),
    )
