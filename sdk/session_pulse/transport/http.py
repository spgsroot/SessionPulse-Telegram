"""HTTP push transport for environments without Kafka.

POST batches to session-pulse-server /api/v1/ingest endpoint.
"""

import json
import logging

logger = logging.getLogger("session_pulse.transport.http")


class HttpTransport:
    def __init__(self, endpoint: str, auth_token: str = ""):
        self._endpoint = endpoint
        self._auth_token = auth_token
        self._session = None
        self._healthy = True

    async def start(self) -> None:
        try:
            import aiohttp
        except ImportError:
            raise ImportError(
                "aiohttp is required for HTTP transport. "
                "Install with: pip install session-pulse[http]"
            )

        headers = {"Content-Type": "application/json"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        timeout = aiohttp.ClientTimeout(total=10, connect=5)
        self._session = aiohttp.ClientSession(
            headers=headers, timeout=timeout
        )
        logger.info(f"HTTP transport started ({self._endpoint})")

    async def stop(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None
        logger.info("HTTP transport stopped")

    async def send_batch(self, events: list[dict]) -> bool:
        if not self._session:
            return False
        try:
            payload = json.dumps({"events": events}, default=str)
            async with self._session.post(
                self._endpoint, data=payload
            ) as resp:
                self._healthy = resp.status < 500
                return resp.status == 200
        except Exception as e:
            logger.error(f"HTTP transport error: {e}")
            self._healthy = False
            return False

    def is_healthy(self) -> bool:
        return self._healthy
