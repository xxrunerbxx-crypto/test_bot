from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import LOG_CHANNEL_ID
from database.db import SlotConflictError, ValidationError, db
from keyboards.calendar_kb import generate_calendar
from keyboards.inline import back_kb, main_menu
from services.booking_service import booking_service
from services.notification_service import notification_service
from services.subscription_service import subscription_service
from utils.scheduler import cancel_job
from utils.states import BookingStates

router = Router()


@router.message(Command("start"))
async def start(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    db.upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name, "client")

    if command.args and command.args.startswith("ref_"):
        ref_value = command.args.replace("ref_", "").strip()
        if ref_value.isdigit():
            await state.update_data(referrer_master_id=int(ref_value))
            return await message.answer(
                "🎁 Реферальный код принят.\nЕсли вы мастер, отправьте /admin для активации бонуса пригласившему."
            )

    if command.args and command.args.isdigit():
        master_id = int(command.args)
        await state.update_data(master_id=master_id)
        profile = db.get_master_profile(master_id)
        portfolio = profile["portfolio_link"] if profile else "https://t.me/telegram"
        try:
            portfolio = db.normalize_portfolio_link(portfolio)
        except Exception:
            portfolio = "https://t.me/telegram"
        await message.answer("💅 Выберите действие:", reply_markup=main_menu(portfolio, master_id))
        return
    await message.answer("Для записи используйте персональную ссылку мастера.")


@router.callback_query(F.data == "to_main")
async def to_main(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    master_id = data.get("master_id")
    if not master_id:
        return await callback.answer("Откройте бота по ссылке мастера.", show_alert=True)
    profile = db.get_master_profile(master_id)
    portfolio = profile["portfolio_link"] if profile else "https://t.me/telegram"
    try:
        portfolio = db.normalize_portfolio_link(portfolio)
    except Exception:
        portfolio = "https://t.me/telegram"
    await callback.message.edit_text("💅 Выберите действие:", reply_markup=main_menu(portfolio, master_id))


@router.callback_query(F.data == "services")
async def show_services(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    master_id = data.get("master_id")
    if not master_id:
        return await callback.answer("Мастер не найден.", show_alert=True)
    profile = db.get_master_profile(master_id)
    if not profile:
        return await callback.answer("Профиль мастера не заполнен.", show_alert=True)
    text = (
        f"<b>💅 Основные услуги:</b>\n{profile['main_services']}\n\n"
        f"<b>✨ Доп. услуги:</b>\n{profile['additional_services']}\n\n"
        f"<b>🛡 Гарантия:</b>\n{profile['warranty']}"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_kb())


@router.callback_query(F.data == "start_booking")
async def start_booking(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    master_id = data.get("master_id")
    if not master_id:
        return await callback.answer("Мастер не найден.", show_alert=True)
    has_access, _ = subscription_service.check_access(master_id)
    if not has_access:
        return await callback.answer("Запись временно закрыта.", show_alert=True)
    maintenance = db.get_maintenance()
    if maintenance["enabled"]:
        return await callback.answer(maintenance["message"], show_alert=True)
    now = datetime.now()
    await callback.message.edit_text(
        "╔══ 💅 <b>Онлайн запись</b> ══╗\n"
        "Выберите дату в календаре ниже.",
        parse_mode="HTML",
        reply_markup=generate_calendar(now.year, now.month, master_id=master_id),
    )

@router.callback_query(F.data.startswith("cal_user_"))
async def client_calendar_switch(callback: CallbackQuery):
    _, _, master_id, year, month = callback.data.split("_")
    await callback.message.edit_text(
        "╔══ 💅 <b>Онлайн запись</b> ══╗\nВыберите дату в календаре ниже.",
        parse_mode="HTML",
        reply_markup=generate_calendar(int(year), int(month), int(master_id), is_admin=False),
    )


@router.callback_query(F.data.startswith("user_date_"))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    date = callback.data.split("_")[2]
    if datetime.strptime(date, "%Y-%m-%d").date() < datetime.now().date():
        return await callback.answer("Нельзя выбрать прошедший день.", show_alert=True)
    data = await state.get_data()
    master_id = data.get("master_id")
    slots = db.get_available_slots(master_id, date)
    if not slots:
        return await callback.answer("Нет свободных слотов.", show_alert=True)
    await state.update_data(date=date)
    builder = InlineKeyboardBuilder()
    for slot in slots:
        builder.button(text=slot["time"], callback_data=f"slot_{slot['id']}_{slot['time']}")
    builder.adjust(3)
    builder.button(text="⬅️ Назад", callback_data="start_booking")
    await callback.message.edit_text(
        f"╔══ ⏰ <b>Свободные слоты</b> ══╗\nДата: <b>{date}</b>\nВыберите удобное время:",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(BookingStates.choosing_time)


@router.callback_query(BookingStates.choosing_time, F.data.startswith("slot_"))
async def ask_name(callback: CallbackQuery, state: FSMContext):
    _, slot_id, slot_time = callback.data.split("_")
    await state.update_data(slot_id=int(slot_id), time=slot_time)
    await state.set_state(BookingStates.entering_name)
    await callback.message.edit_text("Введите имя и фамилию:")


@router.message(BookingStates.entering_name)
async def ask_phone(message: Message, state: FSMContext):
    await state.update_data(name=message.text or "")
    await state.set_state(BookingStates.entering_phone)
    await message.answer("Введите номер телефона или отправьте контакт.")


@router.message(BookingStates.entering_phone)
async def finish_booking(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    phone_raw = message.contact.phone_number if message.contact else (message.text or "")
    maintenance = db.get_maintenance()
    if maintenance["enabled"]:
        return await message.answer(maintenance["message"])
    try:
        booking_id = booking_service.create_booking(
            master_id=int(data["master_id"]),
            user_id=message.from_user.id,
            slot_id=int(data["slot_id"]),
            name=data.get("name", ""),
            phone=phone_raw,
        )
        slot_info = db.get_slot_by_id(int(data["slot_id"]))
        slot_at = slot_info["slot_at"]
        notification_service.schedule_booking_notifications(
            bot=bot,
            booking_id=booking_id,
            user_id=message.from_user.id,
            master_id=int(data["master_id"]),
            slot_at=slot_at,
        )
    except ValidationError:
        return await message.answer("❌ Некорректные данные или уже есть 2 активные записи. Проверьте имя/телефон.")
    except SlotConflictError:
        return await message.answer("Этот слот уже занят. Выберите другой.")
    except Exception:
        return await message.answer("Не удалось оформить запись. Попробуйте позже.")

    profile = db.get_master_profile(int(data["master_id"]))
    portfolio = profile["portfolio_link"] if profile else "https://t.me/telegram"
    try:
        portfolio = db.normalize_portfolio_link(portfolio)
    except Exception:
        portfolio = "https://t.me/telegram"
    await message.answer(
        "╔══ ✅ <b>Запись подтверждена</b> ══╗\n"
        f"📅 Дата: <b>{data['date']}</b>\n"
        f"⏰ Время: <b>{slot_info['label']}</b>\n\n"
        "Можете закрывать меню 🙂",
        parse_mode="HTML",
        reply_markup=main_menu(portfolio, int(data["master_id"])),
    )
    await bot.send_message(
        int(data["master_id"]),
        f"🆕 Новая запись:\n👤 {data.get('name','-')}\n📞 {booking_service.validate_phone(phone_raw)}\n📅 {data['date']} {data['time']}",
    )
    try:
        await bot.send_message(
            LOG_CHANNEL_ID,
            "📥 <b>Новая запись клиента</b>\n\n"
            f"👤 Клиент: <b>{data.get('name','-')}</b>\n"
            f"📞 Телефон: <code>{booking_service.validate_phone(phone_raw)}</code>\n"
            f"🧑‍🔧 Мастер ID: <code>{int(data['master_id'])}</code>\n"
            f"👤 User ID клиента: <code>{message.from_user.id}</code>\n"
            f"📅 Дата/время: <b>{data['date']} {data['time']}</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await state.clear()


@router.callback_query(F.data == "cancel_booking")
async def cancel_booking(callback: CallbackQuery):
    booking = booking_service.cancel_booking(callback.from_user.id)
    if not booking:
        return await callback.answer("Активной записи нет.", show_alert=True)
    cancel_job(booking["reminder_job_id"])
    cancel_job(booking["review_job_id"])
    await callback.bot.send_message(booking["master_id"], "Клиент отменил запись.")
    await callback.answer("Запись отменена.", show_alert=True)


@router.callback_query(F.data == "my_bookings")
async def my_bookings(callback: CallbackQuery, state: FSMContext):
    items = db.list_user_active_bookings(callback.from_user.id)
    if not items:
        return await callback.answer("У вас пока нет активных записей.", show_alert=True)
    text = "📅 <b>Мои записи</b>\n\n"
    builder = InlineKeyboardBuilder()
    for item in items:
        text += f"• #{item['id']} — {item['slot_at']}\n"
        builder.button(text=f"❌ Отменить #{item['id']}", callback_data=f"cancel_booking_{item['id']}")
    builder.adjust(1)
    builder.button(text="⬅️ Назад", callback_data="to_main")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("cancel_booking_"))
async def cancel_booking_specific(callback: CallbackQuery):
    booking_id = int(callback.data.split("_")[-1])
    booking = db.cancel_booking_by_id(callback.from_user.id, booking_id)
    if not booking:
        return await callback.answer("Запись не найдена или уже отменена.", show_alert=True)
    cancel_job(booking["reminder_job_id"])
    cancel_job(booking["review_job_id"])
    await callback.bot.send_message(booking["master_id"], f"Клиент отменил запись #{booking_id}.")
    await callback.answer("Запись отменена.", show_alert=True)


@router.callback_query(F.data == "feedback_suggestion")
async def feedback_suggestion_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BookingStates.waiting_feedback_text)
    await state.update_data(feedback_type="suggestion")
    await callback.message.edit_text("💡 Напишите ваше предложение одним сообщением.")


@router.callback_query(F.data == "feedback_bug")
async def feedback_bug_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BookingStates.waiting_feedback_text)
    await state.update_data(feedback_type="bug")
    await callback.message.edit_text("🐞 Опишите ошибку одним сообщением.")


@router.message(BookingStates.waiting_feedback_text)
async def feedback_text_save(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    feedback_type = data.get("feedback_type", "suggestion")
    text = (message.text or "").strip()
    if not text:
        return await message.answer("Сообщение не может быть пустым.")
    role = "master" if db.is_master_registered(message.from_user.id) else "client"
    db.create_feedback(message.from_user.id, role, feedback_type, text)
    try:
        kind = "Предложение" if feedback_type == "suggestion" else "Ошибка"
        await bot.send_message(
            LOG_CHANNEL_ID,
            f"📝 <b>{kind}</b>\n"
            f"От: <code>{message.from_user.id}</code> ({role})\n\n{text}",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await state.clear()
    await message.answer("✅ Спасибо! Сообщение отправлено владельцу бота.")

@router.callback_query(F.data.startswith("rate_"))
async def rate_master(callback: CallbackQuery):
    _, master_id, booking_id, rating = callback.data.split("_")
    db.save_review(int(booking_id), int(master_id), callback.from_user.id, int(rating))
    await callback.message.edit_text("Спасибо за отзыв! ❤️")
