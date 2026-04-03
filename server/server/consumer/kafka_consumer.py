"""Kafka consumer for observability events."""

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

logger = logging.getLogger("session_pulse.consumer")


class EventConsumer:
    def __init__(self, bootstrap: str, topic: str, group_id: str, processor):
        self._bootstrap = bootstrap
        self._topic = topic
        self._group_id = group_id
        self._processor = processor
        self._consumer: AIOKafkaConsumer | None = None
        self._running = False

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            self._topic,
            bootstrap_servers=self._bootstrap,
            group_id=self._group_id,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        )
        await self._consumer.start()
        self._running = True
        logger.info(
            f"Consumer started (topic={self._topic}, group={self._group_id})"
        )

    async def run(self) -> None:
        """Main consume loop."""
        if not self._consumer:
            await self.start()

        while self._running:
            try:
                result = await self._consumer.getmany(
                    timeout_ms=1000, max_records=5000
                )
                if not result:
                    continue

                batch = []
                for tp, messages in result.items():
                    for msg in messages:
                        batch.append(msg.value)

                if batch:
                    await self._processor.process_batch(batch)
                    await self._consumer.commit()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Consumer error: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def stop(self) -> None:
        self._running = False
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None
        logger.info("Consumer stopped")
