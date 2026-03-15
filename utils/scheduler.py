from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from config import TOKEN
from aiogram import Bot

scheduler = AsyncIOScheduler()

async def send_reminder(bot: Bot, user_id: int, date_time: str):
    try:
        await bot.send_message(user_id, f"🔔 <b>Напоминание!</b>\n\nВы записаны на завтра в {date_time.split(' ')[1]}.\nЖдём вас! ❤️", parse_mode="HTML")
    except:
        pass

def schedule_reminder(bot: Bot, user_id: int, date_str: str, time_str: str):
    # Дата-время записи: 2023-12-31 14:00
    exec_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M") - timedelta(hours=24)
    
    if exec_time > datetime.now():
        job = scheduler.add_job(
            send_reminder,
            trigger='date',
            run_date=exec_time,
            args=[bot, user_id, f"{date_str} {time_str}"]
        )
        return job.id
    return None