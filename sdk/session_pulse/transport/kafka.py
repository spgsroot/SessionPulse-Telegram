"""Kafka/Redpanda transport.

Uses AIOKafkaProducer with same config pattern as backend/RedpandaClient.py:
- acks="all", enable_idempotence=True
- JSON serialization with str default for datetime
- Key = entity_id for partition affinity
"""

import asyncio
import json
import logging

logger = logging.getLogger("session_pulse.transport.kafka")


class KafkaTransport:
    def __init__(self, bootstrap_servers: str, topic: str):
        self._bootstrap = bootstrap_servers
        self._topic = topic
        self._producer = None
        self._healthy = False

    async def start(self) -> None:
        try:
            from aiokafka import AIOKafkaProducer
        except ImportError:
            raise ImportError(
                "aiokafka is required for Kafka transport. "
                "Install with: pip install session-pulse[kafka]"
            )

        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap,
            value_serializer=lambda v: json.dumps(v, default=str).encode(
                "utf-8"
            ),
            acks="all",
            enable_idempotence=True,
        )
        await self._producer.start()
        self._healthy = True
        logger.info(f"Kafka transport started ({self._bootstrap})")

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            self._producer = None
        self._healthy = False
        logger.info("Kafka transport stopped")

    async def send_batch(self, events: list[dict]) -> bool:
        if not self._producer:
            return False
        try:
            tasks = []
            for event in events:
                key = event.get("entity_id", "").encode("utf-8")
                tasks.append(
                    self._producer.send(self._topic, value=event, key=key)
                )
            results = await asyncio.gather(*tasks, return_exceptions=True)
            errors = [r for r in results if isinstance(r, Exception)]
            if errors:
                logger.warning(
                    f"Kafka send: {len(errors)}/{len(tasks)} failed"
                )
            self._healthy = True
            return len(errors) < len(tasks)
        except Exception as e:
            logger.error(f"Kafka batch send failed: {e}")
            self._healthy = False
            return False

    def is_healthy(self) -> bool:
        return self._healthy
