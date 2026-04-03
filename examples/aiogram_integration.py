"""Example: Integrating SessionPulse with an Aiogram 3.x Telegram bot."""

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from session_pulse import SessionPulse
from session_pulse.integrations.aiogram import instrument_aiogram

pulse = SessionPulse(
    service_name="my-bot",
    transport="kafka",
    kafka_bootstrap="localhost:9092",
)


async def main():
    bot = Bot(token="YOUR_BOT_TOKEN")
    dp = Dispatcher(storage=MemoryStorage())

    # Initialize SessionPulse
    try:
        await pulse.start()
        instrument_aiogram(dp, pulse)  # auto-tracks handler latency, errors
    except Exception as e:
        print(f"SessionPulse init failed (continuing without): {e}")

    @dp.message()
    async def echo(message: Message):
        # Custom metrics alongside auto-tracking
        pulse.counter("user_messages", "bot", "echo",
                      tags={"user_id": str(message.from_user.id)})
        await message.answer(message.text)

    try:
        await dp.start_polling(bot)
    finally:
        await pulse.stop()


if __name__ == "__main__":
    asyncio.run(main())
