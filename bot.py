import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import LOG_CHANNEL_ID, TOKEN
from handlers import admin, client, master
from services.notification_service import notification_service
from utils.scheduler import scheduler


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not TOKEN:
        raise RuntimeError("Set BOT_TOKEN env variable")
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(admin.router)
    dp.include_router(master.router)
    dp.include_router(client.router)

    scheduler.start()
    notification_service.restore_jobs(bot)
    try:
        await bot.send_message(
            LOG_CHANNEL_ID,
            "🟢 <b>Бот запущен</b>\nСервис успешно стартовал и готов к работе.",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())