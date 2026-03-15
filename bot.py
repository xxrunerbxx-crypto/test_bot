import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import TOKEN
from handlers import user, admin
from database.db import db
from utils.scheduler import scheduler, send_reminder

async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    # Регистрация роутеров
    dp.include_router(admin.router)
    dp.include_router(user.router)

    # Восстановление напоминаний из БД
    bookings = db.get_all_active_bookings()
    for u_id, dt_str, job_id in bookings:
        # Простая логика: если время еще не вышло - можно пересоздать 
        # (в данном примере для упрощения оставляем планирование новых)
        pass

    scheduler.start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")