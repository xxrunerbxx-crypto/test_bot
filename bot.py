import asyncio
import logging
import time  # Импортируем для замера времени
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update

from config import TOKEN
from handlers import user, admin
from database.db import db
from utils.scheduler import scheduler, send_reminder

# =========================================================
# ВРЕМЕННЫЙ ТЕСТОВЫЙ БЛОК (MIDDLEWARE ДЛЯ ЗАМЕРА СКОРОСТИ)
# =========================================================
# Этот блок будет выводить в консоль время обработки каждого действия.
# Если захочешь отключить его, просто удали или закомментируй этот блок.

async def timing_middleware(handler, event, data):
    start_time = time.perf_counter()  # Засекаем время
    result = await handler(event, data)  # Выполняем хендлер
    execution_time = time.perf_counter() - start_time  # Считаем разницу
    
    # Выводим результат в консоль сервера
    print(f"--- [ТЕСТ СКОРОСТИ] Событие обработано за: {execution_time:.4f} сек. ---")
    return result

# =========================================================

async def restore_reminders(bot: Bot):
    """
    Функция восстановления напоминаний из базы данных.
    Нужна, чтобы после перезагрузки сервера бот 'вспомнил' о записях.
    """
    logging.info("Восстановление напоминаний из базы данных...")
    bookings = db.get_all_active_bookings()
    
    count = 0
    for user_id, date_time, job_id in bookings:
        try:
            appt_time = datetime.strptime(date_time, "%Y-%m-%d %H:%M")
            reminder_time = appt_time - timedelta(hours=24)
            
            # Если время напоминания еще в будущем
            if reminder_time > datetime.now():
                # Если такой задачи еще нет в планировщике, добавляем
                if not scheduler.get_job(str(job_id)):
                    scheduler.add_job(
                        send_reminder,
                        trigger='date',
                        run_date=reminder_time,
                        args=[bot, user_id, date_time],
                        id=str(job_id)
                    )
                    count += 1
        except Exception as e:
            logging.error(f"Ошибка при восстановлении записи {job_id}: {e}")
    
    logging.info(f"Восстановлено напоминаний: {count}")

async def main():
    # Настройка красивого вывода логов в консоль
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    
    # Создаем объект бота
    # DefaultBotProperties позволяет не писать в каждом сообщении parse_mode="HTML"
    bot = Bot(
        token=TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()

    # РЕГИСТРАЦИЯ ТЕСТОВОГО MIDDLEWARE
    # (Подключаем нашу 'замерялку' скорости к диспетчеру)
    dp.update.outer_middleware()(timing_middleware)

    # Регистрация обработчиков (handlers)
    dp.include_router(admin.router)  # Админку ставим первой
    dp.include_router(user.router)

    # Инициализация и запуск планировщика задач (Reminders)
    scheduler.start()
    
    # Восстанавливаем задачи из БД перед началом работы
    await restore_reminders(bot)

    # Удаляем все сообщения, которые пришли боту, пока он был выключен (drop_pending_updates)
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запуск бесконечного цикла прослушивания обновлений
    logging.info("Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен пользователем")