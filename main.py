import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from database import db
from handlers import common, admin, booking

async def cleanup_task():
    while True:
        await db.cleanup_expired_locks()
        await asyncio.sleep(60)

async def main():
    logging.basicConfig(level=logging.INFO)
    
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    # Подключаем роутеры (файлы с логикой)
    dp.include_router(admin.router)
    dp.include_router(common.router)
    dp.include_router(booking.router)

    await db.create_tables()
    asyncio.create_task(cleanup_task())
    
    print("Бот запущен! 🚀")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())