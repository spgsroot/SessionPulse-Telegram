"""No-op transport: silently discards all events. Default when disabled."""


class NoopTransport:
    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def send_batch(self, events: list[dict]) -> bool:
        return True

    def is_healthy(self) -> bool:
        return True
