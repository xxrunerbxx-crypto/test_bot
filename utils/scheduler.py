from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from aiogram import Bot
import logging

# Импортируем клавиатуру для отзывов (звездочки) из твоего файла
from keyboards.inline import review_kb

scheduler = AsyncIOScheduler()

# Утилита для снятия reminder-задач по job_id
def cancel_reminder_job(job_id: str):
    try:
        if scheduler.get_job(str(job_id)):
            scheduler.remove_job(str(job_id))
    except Exception:
        # Если job уже исчез или не найден — это не критично
        pass

# --- ПУНКТ 3: ЛОГИКА ОТЗЫВОВ ---

async def ask_review(bot: Bot, user_id: int, master_id: int):
    """Функция, которая отправит сообщение с просьбой оценить мастера"""
    try:
        await bot.send_message(
            user_id, 
            "🌟 <b>Как прошёл ваш визит?</b>\n\nПожалуйста, оцените работу мастера. Это поможет другим клиентам сделать правильный выбор! ❤️", 
            reply_markup=review_kb(master_id),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Не удалось отправить запрос отзыва пользователю {user_id}: {e}")

def schedule_feedback(bot: Bot, user_id: int, master_id: int, date_str: str, time_str: str):
    """Создает задачу опроса через 2-3 часа после начала записи"""
    try:
        full_str = f"{date_str.strip()} {time_str.strip()}"
        event_dt = datetime.strptime(full_str, "%Y-%m-%d %H:%M")
        
        # Ставим опрос через 2 часа после начала записи (предполагаем, что сеанс завершен)
        review_time = event_dt + timedelta(hours=2)
        
        if review_time > datetime.now():
            scheduler.add_job(
                ask_review,
                trigger='date',
                run_date=review_time,
                args=[bot, user_id, master_id]
            )
            logging.info(f"Запланирован опрос для {user_id} на {review_time}")
    except Exception as e:
        logging.error(f"Ошибка в schedule_feedback: {e}")

# --- ЛОГИКА НАПОМИНАНИЙ ---

async def send_reminder(bot: Bot, user_id: int, date_time: str):
    """Функция, которая отправит сообщение-напоминание за 24 часа"""
    try:
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
        d = date_str.strip()
        t = time_str.strip()
        full_str = f"{d} {t}"
        
        try:
            event_dt = datetime.strptime(full_str, "%Y-%m-%d %H:%M")
        except ValueError:
            full_str = full_str.replace(f"{d}-{t}", f"{d} {t}")
            event_dt = datetime.strptime(full_str, "%Y-%m-%d %H:%M")

        reminder_time = event_dt - timedelta(hours=24)
        
        if reminder_time > datetime.now():
            job = scheduler.add_job(
                send_reminder,
                trigger='date',
                run_date=reminder_time,
                args=[bot, user_id, full_str]
            )
            return job.id
        else:
            logging.info(f"До записи меньше 24 часов, напоминание не ставится.")
            return None
            
    except Exception as e:
        logging.error(f"Ошибка в schedule_reminder: {e}")
        return None