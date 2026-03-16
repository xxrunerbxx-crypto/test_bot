import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import TOKEN, CHANNEL_ID
from handlers import user, admin
from database.db import db
from utils.scheduler import scheduler, send_reminder

async def restore_reminders(bot: Bot):
    """
    Восстановление напоминаний из базы данных.
    Исправлено: теперь не падает, если дата в базе записана криво.
    """
    logging.info("Восстановление напоминаний из базы данных...")
    bookings = db.get_all_active_bookings()
    
    count = 0
    for user_id, date_time, job_id in bookings:
        # Пропускаем записи без напоминаний
        if job_id == "no_reminder":
            continue
            
        try:
            # Исправляем возможную ошибку формата (заменяем дефис между датой и временем на пробел)
            clean_dt = date_time.replace(" ", " ") # на всякий случай
            if "-" in clean_dt and clean_dt.count("-") == 3: # если формат 2024-05-20-13:00
                parts = clean_dt.rsplit("-", 1)
                clean_dt = f"{parts[0]} {parts[1]}"

            appt_time = datetime.strptime(clean_dt, "%Y-%m-%d %H:%M")
            reminder_time = appt_time - timedelta(hours=24)
            
            if reminder_time > datetime.now():
                if not scheduler.get_job(str(job_id)):
                    scheduler.add_job(
                        send_reminder,
                        trigger='date',
                        run_date=reminder_time,
                        args=[bot, user_id, clean_dt],
                        id=str(job_id)
                    )
                    count += 1
        except Exception as e:
            logging.error(f"Ошибка при восстановлении записи {job_id}: {e}")
    
    logging.info(f"Восстановлено напоминаний: {count}")

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    
    # 1. Создаем объект бота
    bot = Bot(
        token=TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # --- ТЕСТ КАНАЛА (ТЕПЕРЬ ПРАВИЛЬНО) ---
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text="🛠 Бот запущен и подключен к каналу!")
        print("✅ Тест канала пройден!")
    except Exception as e:
        print(f"❌ Тест канала провален: {e}")
    # --------------------------------------

    dp = Dispatcher()

    # Регистрация роутеров
    dp.include_router(admin.router)
    dp.include_router(user.router)

    # Запуск планировщика
    scheduler.start()
    
    # Восстанавливаем задачи
    await restore_reminders(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")