from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from aiogram import Bot
import logging

scheduler = AsyncIOScheduler()

async def send_reminder(bot: Bot, user_id: int, date_time: str):
    """Функция, которая отправит сообщение пользователю"""
    try:
        # Извлекаем только время для красивого текста
        # Если date_time это "2024-05-20 13:00", возьмем "13:00"
        display_time = date_time.split(" ")[-1] 
        await bot.send_message(
            user_id, 
            f"🔔 <b>Напоминание!</b>\n\nВы записаны на завтра в {display_time}.\nЖдём вас! ❤️", 
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Не удалось отправить напоминание: {e}")

def schedule_reminder(bot: Bot, user_id: int, date_str: str, time_str: str):
    """Создает задачу напоминания за 24 часа до записи"""
    try:
        # Убираем лишние пробелы и символы
        d = date_str.strip()
        t = time_str.strip()
        
        # Пробуем собрать дату. Мы ожидаем ГГГГ-ММ-ДД и ЧЧ:ММ
        # Если в d уже есть время, strptime выдаст ошибку, которую мы поймаем
        full_str = f"{d} {t}"
        
        # Пытаемся распарсить дату
        try:
            event_dt = datetime.strptime(full_str, "%Y-%m-%d %H:%M")
        except ValueError:
            # Если дата пришла в другом формате (например ГГГГ-ММ-ДД-ЧЧ:ММ)
            # заменим тире перед временем на пробел
            full_str = full_str.replace(f"{d}-{t}", f"{d} {t}")
            event_dt = datetime.strptime(full_str, "%Y-%m-%d %H:%M")

        # Время напоминания — за 24 часа до события
        reminder_time = event_dt - timedelta(hours=24)
        
        # Если до события еще больше 24 часов, ставим задачу
        if reminder_time > datetime.now():
            job = scheduler.add_job(
                send_reminder,
                trigger='date',
                run_date=reminder_time,
                args=[bot, user_id, full_str]
            )
            return job.id
        else:
            logging.info(f"Напоминание для {user_id} не создано: до записи меньше 24 часов.")
            return None
            
    except Exception as e:
        logging.error(f"Ошибка в schedule_reminder: {e}")
        return None