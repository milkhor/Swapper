import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

from config import BOT_TOKEN, WEBHOOK_HOST, WEBHOOK_PATH, WEBHOOK_URL
from database.db import init_db
from handlers import aml, history, start, exchange, status, admin, buywithcard, language
from services.checker import check_swaps
from services.logger import setup_logging
from services.webhook import create_app

setup_logging()
logger = logging.getLogger(__name__)

# Порт для aiohttp — Railway задаёт через переменную PORT
PORT = int(os.getenv("PORT", 8080))


async def on_startup(bot: Bot, dp: Dispatcher):
    """Runs on bot startup."""
    await init_db()
    asyncio.create_task(check_swaps(bot))

    if WEBHOOK_HOST:
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Webhook set: {WEBHOOK_URL}")
    else:
        logger.info("WEBHOOK_HOST not set — falling back to polling")


async def on_shutdown(bot: Bot):
    """Runs on bot shutdown."""
    logger.info("Shutting down...")
    if WEBHOOK_HOST:
        await bot.delete_webhook()
    await bot.session.close()


async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(exchange.router)  # first: handles swap_back and exchange states
    dp.include_router(start.router)
    dp.include_router(language.router)
    dp.include_router(status.router)
    dp.include_router(history.router)
    dp.include_router(admin.router)
    dp.include_router(aml.router)
    dp.include_router(buywithcard.router)

    await on_startup(bot, dp)

    if WEBHOOK_HOST:
        # Webhook mode
        app = create_app(bot, dp, WEBHOOK_PATH)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
        await site.start()
        logger.info(f"Webhook server running on port {PORT}")

        # Держим процесс живым
        try:
            await asyncio.Event().wait()
        finally:
            await on_shutdown(bot)
            await runner.cleanup()
    else:
        # Polling fallback (для локальной разработки)
        try:
            await dp.start_polling(bot)
        finally:
            await on_shutdown(bot)


if __name__ == "__main__":
    asyncio.run(main())