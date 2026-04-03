"""Example: Integrating SessionPulse with a Quart web application."""

import asyncio

from quart import Quart

from session_pulse import AccountState, SessionPulse
from session_pulse.integrations.quart import instrument_quart

app = Quart(__name__)

pulse = SessionPulse(
    service_name="my-web-api",
    transport="kafka",
    kafka_bootstrap="localhost:9092",
)


@app.before_serving
async def startup():
    try:
        await pulse.start()
        instrument_quart(app, pulse)  # auto-tracks request latency, errors
    except Exception as e:
        print(f"SessionPulse init failed (continuing without): {e}")


@app.after_serving
async def shutdown():
    await pulse.stop()


@app.route("/api/accounts/<phone>/start")
async def start_monitoring(phone: str):
    pulse.account_state(phone, AccountState.MONITORING)
    pulse.event("session", phone, "monitoring_started")
    return {"status": "ok"}


@app.route("/api/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    app.run(port=8000)
