from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import db
from keyboards.calendar_kb import generate_calendar
from services.subscription_service import subscription_service
from utils.states import MasterStates

router = Router()


def master_menu(days_left: str):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📅 Управление слотами", callback_data="m_calendar"))
    kb.row(InlineKeyboardButton(text="📊 Моя статистика", callback_data="m_stats"))
    kb.row(InlineKeyboardButton(text="⚙️ Настройки услуг", callback_data="m_services"))
    kb.row(InlineKeyboardButton(text="📸 Ссылка на портфолио", callback_data="m_portfolio"))
    kb.row(InlineKeyboardButton(text=f"💎 Подписка ({days_left} дн.)", callback_data="m_subscription_info"))
    return kb.as_markup()


async def render_master_main(target_message, user_id: int, bot):
    access, days_left = subscription_service.check_access(user_id)
    if not access:
        await target_message.edit_text(
            "⚠️ <b>Подписка закончилась</b>\n\nДля продления подписки напишите:\n<a href='https://t.me/ivan8954'>@ivan8954</a>",
            parse_mode="HTML",
        )
        return
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={user_id}"
    await target_message.edit_text(
        "🛠 <b>Панель мастера</b>\n\n"
        f"Осталось дней подписки: <b>{days_left}</b>\n\n"
        "Ваша ссылка для записи клиентов:\n"
        f"<code>{link}</code>\n"
        "Нажмите на код выше, чтобы скопировать ссылку.",
        parse_mode="HTML",
        reply_markup=master_menu(days_left),
    )


async def _render_day(message, master_id: int, date: str):
    slots = db.get_admin_slots(master_id, date)
    text = f"Дата: <b>{date}</b>\n\n"
    if not slots:
        text += "Слотов пока нет.\n"
    for slot in slots:
        text += f"{'🔴' if slot['booked'] else '🟢'} {slot['time']}\n"
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="⚡ Авто (10:00-19:00)", callback_data=f"m_auto_{date}"))
    kb.row(InlineKeyboardButton(text="➕ Добавить свое время", callback_data=f"m_addslot_{date}"))
    kb.row(InlineKeyboardButton(text="🗑 Очистить свободные", callback_data=f"m_clear_{date}"))
    kb.row(InlineKeyboardButton(text="⬅️ Назад к календарю", callback_data="m_calendar"))
    kb.row(InlineKeyboardButton(text="🏠 В главное меню", callback_data="m_main"))
    await message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())


@router.message(Command("admin"))
async def master_admin(message: Message, state: FSMContext):
    await state.clear()
    subscription_service.ensure_master(message.from_user.id)
    access, days_left = subscription_service.check_access(message.from_user.id)
    if not access:
        return await message.answer(
            "⚠️ <b>Подписка закончилась</b>\n\nДля продления подписки напишите:\n<a href='https://t.me/ivan8954'>@ivan8954</a>",
            parse_mode="HTML",
        )
    me = await message.bot.get_me()
    link = f"https://t.me/{me.username}?start={message.from_user.id}"
    await message.answer(
        "🛠 <b>Панель мастера</b>\n\n"
        f"Осталось дней подписки: <b>{days_left}</b>\n\n"
        "Ваша ссылка для записи клиентов:\n"
        f"<code>{link}</code>\n"
        "Нажмите на код выше, чтобы скопировать ссылку.",
        parse_mode="HTML",
        reply_markup=master_menu(days_left),
    )


@router.callback_query(F.data == "m_main")
async def m_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await render_master_main(callback.message, callback.from_user.id, callback.bot)


@router.callback_query(F.data == "m_stats")
async def m_stats(callback: CallbackQuery):
    access, days_left = subscription_service.check_access(callback.from_user.id)
    if not access:
        return await callback.message.edit_text(
            "⚠️ Подписка закончилась.\nДля продления напишите: @ivan8954"
        )
    stats = db.get_master_stats(callback.from_user.id)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="m_main"))
    await callback.message.edit_text(
        f"📊 <b>Ваша статистика</b>\n\n"
        f"👥 Всего клиентов: <b>{stats['total']}</b>\n"
        f"📅 Активных записей: <b>{stats['active']}</b>\n"
        f"⭐ Рейтинг: <b>{stats['rating']}</b>\n"
        f"💎 Подписка: <b>{days_left} дн.</b>",
        parse_mode="HTML",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data == "m_calendar")
async def m_calendar(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    now = datetime.now()
    await callback.message.edit_text(
        "📅 Выберите дату:",
        reply_markup=generate_calendar(now.year, now.month, callback.from_user.id, is_admin=True),
    )


@router.callback_query(F.data.startswith("cal_admin_"))
async def master_calendar_switch(callback: CallbackQuery):
    _, _, master_id, year, month = callback.data.split("_")
    await callback.message.edit_text(
        "📅 Выберите дату:",
        reply_markup=generate_calendar(int(year), int(month), int(master_id), is_admin=True),
    )


@router.callback_query(F.data.startswith("admin_date_"))
async def m_day(callback: CallbackQuery):
    date = callback.data.split("_")[2]
    if datetime.strptime(date, "%Y-%m-%d").date() < datetime.now().date():
        return await callback.answer("Прошедшие дни недоступны.", show_alert=True)
    await _render_day(callback.message, callback.from_user.id, date)


@router.callback_query(F.data.startswith("m_auto_"))
async def m_auto(callback: CallbackQuery):
    date = callback.data.split("_")[2]
    for t in ["10:00", "11:30", "13:00", "14:30", "16:00", "17:30", "19:00"]:
        db.add_slot(callback.from_user.id, f"{date} {t}")
    await _render_day(callback.message, callback.from_user.id, date)


@router.callback_query(F.data.startswith("m_addslot_"))
async def m_addslot_start(callback: CallbackQuery, state: FSMContext):
    date = callback.data.split("_")[2]
    await state.set_state(MasterStates.waiting_custom_slot)
    await state.update_data(slot_date=date)
    await callback.message.edit_text(
        f"Введите время для {date} в формате HH:MM\nНапример: 09:00 или 18:45"
    )


@router.message(MasterStates.waiting_custom_slot)
async def m_addslot_save(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    data = await state.get_data()
    date = data.get("slot_date")
    parts = text.split(":")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return await message.answer("❌ Неверный формат. Нужен HH:MM")
    hh = int(parts[0])
    mm = int(parts[1])
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        return await message.answer("❌ Время вне диапазона. Нужен HH:MM")
    db.add_slot(message.from_user.id, f"{date} {hh:02d}:{mm:02d}")
    await state.clear()
    await message.answer(f"✅ Слот {date} {hh:02d}:{mm:02d} добавлен.\nОткройте /admin -> управление слотами.")


@router.callback_query(F.data.startswith("m_clear_"))
async def m_clear(callback: CallbackQuery):
    date = callback.data.split("_")[2]
    db.clear_free_slots_for_date(callback.from_user.id, date)
    await _render_day(callback.message, callback.from_user.id, date)


@router.callback_query(F.data == "m_services")
async def m_services_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(MasterStates.choosing_services_mode)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🖼 Загрузить фото прайса", callback_data="m_services_photo_mode"))
    kb.row(InlineKeyboardButton(text="✍️ Заполнить вручную", callback_data="m_services_manual_mode"))
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="m_main"))
    await callback.message.edit_text("Выберите способ заполнения услуг:", reply_markup=kb.as_markup())


@router.callback_query(F.data == "m_services_photo_mode")
async def m_services_photo_mode(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MasterStates.waiting_price_photo)
    await callback.message.edit_text("Пришлите фото прайса.")


@router.message(MasterStates.waiting_price_photo, F.photo)
async def m_services_price_photo(message: Message, state: FSMContext):
    db.update_master_profile(message.from_user.id, "photo_id", message.photo[-1].file_id)
    await state.clear()
    await message.answer("✅ Фото прайса сохранено.")


@router.callback_query(F.data == "m_services_manual_mode")
async def m_services_manual_mode(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MasterStates.waiting_main)
    await callback.message.edit_text("Шаг 1/4: Основные услуги")


@router.message(MasterStates.waiting_main)
async def m_services_2(message: Message, state: FSMContext):
    db.update_master_profile(message.from_user.id, "main_services", message.text or "")
    await state.set_state(MasterStates.waiting_additional)
    await message.answer("Шаг 2/4: Доп. услуги")


@router.message(MasterStates.waiting_additional)
async def m_services_3(message: Message, state: FSMContext):
    db.update_master_profile(message.from_user.id, "additional_services", message.text or "")
    await state.set_state(MasterStates.waiting_warranty)
    await message.answer("Шаг 3/4: Гарантия")


@router.message(MasterStates.waiting_warranty)
async def m_services_4(message: Message, state: FSMContext):
    db.update_master_profile(message.from_user.id, "warranty", message.text or "")
    await state.set_state(MasterStates.waiting_photo)
    await message.answer("Шаг 4/4: Отправьте фото работ или /skip")


@router.message(MasterStates.waiting_photo, F.photo)
async def m_services_photo(message: Message, state: FSMContext):
    db.update_master_profile(message.from_user.id, "photo_id", message.photo[-1].file_id)
    await state.clear()
    await message.answer("✅ Профиль услуг обновлен.")


@router.message(Command("skip"), MasterStates.waiting_photo)
async def m_skip_photo(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("✅ Профиль услуг обновлен без фото.")


@router.callback_query(F.data == "m_portfolio")
async def m_portfolio_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(MasterStates.waiting_portfolio)
    await callback.message.edit_text(
        "Пришлите ссылку на портфолио.\nМожно: https://..., t.me/username или @username"
    )


@router.message(MasterStates.waiting_portfolio)
async def m_portfolio_save(message: Message, state: FSMContext):
    try:
        normalized = db.normalize_portfolio_link(message.text or "")
    except Exception:
        return await message.answer("❌ Неверный формат. Пример: https://t.me/username или @username")
    db.update_master_profile(message.from_user.id, "portfolio_link", normalized)
    await state.clear()
    await message.answer("✅ Ссылка сохранена.")


@router.callback_query(F.data == "m_subscription_info")
async def m_subscription_info(callback: CallbackQuery):
    _, days_left = subscription_service.check_access(callback.from_user.id)
    text = (
        "💎 <b>Подписка</b>\n\n"
        f"Осталось дней: <b>{days_left}</b>\n\n"
        "Для продления подписки напишите:\n"
        "<a href='https://t.me/ivan8954'>@ivan8954</a>"
    )
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="Написать @ivan8954", url="https://t.me/ivan8954"))
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="m_main"))
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
