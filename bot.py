import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import TOKEN
from handlers import user, admin
from database.db import db
from utils.scheduler import scheduler, send_reminder

async def restore_reminders(bot: Bot):
    """Восстановление напоминаний из базы данных при перезапуске бота"""
    bookings = db.get_all_active_bookings()
    for user_id, date_time, job_id in bookings:
        try:
            # Превращаем строку из базы в объект времени
            appt_time = datetime.strptime(date_time, "%Y-%m-%d %H:%M")
            # Вычисляем время напоминания (за 24 часа)
            reminder_time = appt_time - timedelta(hours=24)
            
            # Если время напоминания еще не наступило, добавляем в планировщик
            if reminder_time > datetime.now():
                # Проверяем, нет ли уже такой задачи в планировщике, чтобы не дублировать
                if not scheduler.get_job(str(job_id)):
                    scheduler.add_job(
                        send_reminder,
                        trigger='date',
                        run_date=reminder_time,
                        args=[bot, user_id, date_time],
                        id=str(job_id)
                    )
        except Exception as e:
            logging.error(f"Ошибка при восстановлении задачи {job_id}: {e}")

async def main():
    # Настройка логирования
    logging.basicConfig(level=logging.INFO)
    
    # Инициализация бота с поддержкой HTML по умолчанию
    bot = Bot(
        token=TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # Регистрация роутеров
    dp.include_router(admin.router)
    dp.include_router(user.router)

    # Запуск планировщика
    scheduler.start()
    
    # Восстановление задач из базы данных
    await restore_reminders(bot)

    # Пропускаем накопившиеся обновления и запускаем бота
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот выключен")