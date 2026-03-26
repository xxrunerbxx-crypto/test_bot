from datetime import datetime, timedelta

from aiogram import Bot

from database.db import db
from keyboards.inline import review_kb
from utils.scheduler import scheduler


class NotificationService:
    async def send_reminder(self, bot: Bot, user_id: int, slot_at: str):
        dt = datetime.strptime(slot_at, "%Y-%m-%d %H:%M")
        await bot.send_message(
            user_id,
            f"🔔 <b>Напоминание!</b>\n\nВы записаны на {dt.strftime('%d.%m %H:%M')}.",
            parse_mode="HTML",
        )

    async def ask_review(self, bot: Bot, user_id: int, master_id: int, booking_id: int):
        await bot.send_message(
            user_id,
            "🌟 <b>Как прошел ваш визит?</b>\nОцените мастера:",
            parse_mode="HTML",
            reply_markup=review_kb(master_id, booking_id),
        )

    def schedule_booking_notifications(self, bot: Bot, booking_id: int, user_id: int, master_id: int, slot_at: str):
        dt = datetime.strptime(slot_at, "%Y-%m-%d %H:%M")
        reminder_job_id = None
        review_job_id = None

        reminder_at = dt - timedelta(hours=24)
        if reminder_at > datetime.now():
            reminder_job = scheduler.add_job(
                self.send_reminder,
                trigger="date",
                run_date=reminder_at,
                args=[bot, user_id, slot_at],
            )
            reminder_job_id = str(reminder_job.id)

        review_at = dt + timedelta(hours=2)
        if review_at > datetime.now():
            review_job = scheduler.add_job(
                self.ask_review,
                trigger="date",
                run_date=review_at,
                args=[bot, user_id, master_id, booking_id],
            )
            review_job_id = str(review_job.id)

        db.set_booking_jobs(booking_id, reminder_job_id, review_job_id)

    def restore_jobs(self, bot: Bot):
        for booking in db.get_active_bookings_for_restore():
            if booking.reminder_job_id and scheduler.get_job(booking.reminder_job_id):
                continue
            self.schedule_booking_notifications(bot, booking.booking_id, booking.user_id, booking.master_id, booking.slot_at)


notification_service = NotificationService()
