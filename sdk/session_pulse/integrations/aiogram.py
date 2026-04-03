"""Aiogram 3.x auto-instrumentation.

Tracks handler execution time, command usage, and error rates.
"""

import time


class PulseAiogramMiddleware:
    """Middleware that tracks handler execution metrics."""

    def __init__(self, pulse):
        self._pulse = pulse

    async def __call__(self, handler, event, data):
        from aiogram.types import CallbackQuery, Message

        start = time.monotonic()

        if isinstance(event, Message):
            event_name = (
                event.text.split()[0] if event.text else "unknown"
            )
            event_category = "message"
        elif isinstance(event, CallbackQuery):
            event_name = event.data or "unknown"
            event_category = "callback"
        else:
            event_name = type(event).__name__
            event_category = "other"

        try:
            result = await handler(event, data)
            latency = (time.monotonic() - start) * 1000
            self._pulse.histogram(
                "bot_handler_duration_ms",
                "service",
                self._pulse._service_name,
                latency,
                tags={"handler": event_name, "type": event_category},
            )
            self._pulse.counter(
                "bot_commands",
                "service",
                self._pulse._service_name,
                tags={"command": event_name},
            )
            return result
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            self._pulse.histogram(
                "bot_handler_duration_ms",
                "service",
                self._pulse._service_name,
                latency,
                tags={
                    "handler": event_name,
                    "error": type(e).__name__,
                },
            )
            self._pulse.counter(
                "bot_errors",
                "service",
                self._pulse._service_name,
                tags={
                    "handler": event_name,
                    "error": type(e).__name__,
                },
            )
            raise


def instrument_aiogram(dp, pulse) -> None:
    """Register pulse middleware on aiogram dispatcher."""
    from aiogram import BaseMiddleware

    class _Wrapper(BaseMiddleware, PulseAiogramMiddleware):
        def __init__(self, p):
            BaseMiddleware.__init__(self)
            PulseAiogramMiddleware.__init__(self, p)

    middleware = _Wrapper(pulse)
    dp.message.middleware(middleware)
    dp.callback_query.middleware(middleware)
