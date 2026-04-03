"""Quart web framework auto-instrumentation.

Tracks request latency, status codes, and error rates per endpoint.
"""

import time


def instrument_quart(app, pulse) -> None:
    """Register before/after request hooks for observability."""
    from quart import request

    @app.before_request
    async def _pulse_before():
        request._pulse_start = time.monotonic()

    @app.after_request
    async def _pulse_after(response):
        start = getattr(request, "_pulse_start", None)
        if start is not None:
            latency = (time.monotonic() - start) * 1000
            endpoint = request.endpoint or request.path
            pulse.histogram(
                "http_request_duration_ms",
                "service",
                pulse._service_name,
                latency,
                tags={
                    "endpoint": endpoint,
                    "method": request.method,
                    "status": str(response.status_code),
                },
            )
            if response.status_code >= 500:
                pulse.counter(
                    "http_errors",
                    "service",
                    pulse._service_name,
                    tags={
                        "endpoint": endpoint,
                        "status": str(response.status_code),
                    },
                )
        return response
