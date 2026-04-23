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
    """Компактное главное меню мастера"""
    kb = InlineKeyboardBuilder()
    # Основные действия (2 кнопки в ряду)
    kb.row(
        InlineKeyboardButton(text="📅 Управление слотами", callback_data="m_calendar"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="m_stats"),
    )
    # Управление (2 кнопки в ряду)
    kb.row(
        InlineKeyboardButton(text="🧾 Mini-CRM", callback_data="m_crm_clients"),
        InlineKeyboardButton(text="⚙️ Услуги", callback_data="m_services"),
    )
    # Профиль и ссылки (2 кнопки в ряду)
    kb.row(
        InlineKeyboardButton(text="📸 Портфолио", callback_data="m_portfolio"),
        InlineKeyboardButton(text="👤 Профиль", callback_data="m_profile"),
    )
    # Бизнес (2 кнопки в ряду)
    kb.row(
        InlineKeyboardButton(text="🎁 Реферралы", callback_data="m_referral"),
        InlineKeyboardButton(text="💎 Подписка", callback_data="m_subscription_info"),
    )
    # Обратная связь и помощь (1 кнопка)
    kb.row(InlineKeyboardButton(text="💡/🐞 Идея или ошибка", callback_data="m_feedback_menu"))
    kb.adjust(2, 2, 2, 2, 1)
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
    for slot in slots:
        if not slot["booked"]:
            kb.row(InlineKeyboardButton(text=f"❌ Удалить {slot['time']}", callback_data=f"m_del_{slot['id']}_{date}"))
    kb.row(InlineKeyboardButton(text="⚡ Авто (10:00-19:00)", callback_data=f"m_auto_{date}"))
    kb.row(InlineKeyboardButton(text="➕ Добавить время", callback_data=f"m_addslot_{date}"))
    kb.row(InlineKeyboardButton(text="🗑 Очистить свободные", callback_data=f"m_clear_{date}"))
    kb.row(
        InlineKeyboardButton(text="⬅️ К календарю", callback_data="m_calendar"),
        InlineKeyboardButton(text="🏠 В меню", callback_data="m_main"),
    )
    await message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())


@router.message(Command("admin"))
async def master_admin(message: Message, state: FSMContext):
    state_data = await state.get_data()
    await state.clear()
    was_master = db.is_master_registered(message.from_user.id)
    subscription_service.ensure_master(message.from_user.id)
    if not was_master:
        referrer_master_id = state_data.get("referrer_master_id")
        if isinstance(referrer_master_id, int):
            db.apply_referral_bonus(referrer_master_id, message.from_user.id, bonus_points=100)
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
    for t in ["10:00-11:00", "11:30-12:30", "13:00-14:00", "14:30-15:30", "16:00-17:00", "17:30-18:30", "19:00-20:00"]:
        db.add_slot(callback.from_user.id, f"{date} {t}")
    await _render_day(callback.message, callback.from_user.id, date)


@router.callback_query(F.data.startswith("m_addslot_"))
async def m_addslot_start(callback: CallbackQuery, state: FSMContext):
    date = callback.data.split("_")[2]
    await state.set_state(MasterStates.waiting_custom_slot)
    await state.update_data(slot_date=date)
    await callback.message.edit_text(
        f"Введите слот для {date} в формате HH:MM-HH:MM\nНапример: 10:00-11:00"
    )


@router.message(MasterStates.waiting_custom_slot)
async def m_addslot_save(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    data = await state.get_data()
    date = data.get("slot_date")
    if "-" not in text:
        return await message.answer("❌ Неверный формат. Нужен HH:MM-HH:MM")
    start, end = [x.strip() for x in text.split("-", 1)]
    def _valid(t: str):
        p = t.split(":")
        if len(p) != 2 or not p[0].isdigit() or not p[1].isdigit():
            return None
        h = int(p[0]); m = int(p[1])
        if h < 0 or h > 23 or m < 0 or m > 59:
            return None
        return h, m
    st = _valid(start)
    en = _valid(end)
    if not st or not en:
        return await message.answer("❌ Неверный формат. Нужен HH:MM-HH:MM")
    if (en[0], en[1]) <= (st[0], st[1]):
        return await message.answer("❌ Время окончания должно быть позже времени начала.")
    db.add_slot(message.from_user.id, f"{date} {st[0]:02d}:{st[1]:02d}-{en[0]:02d}:{en[1]:02d}")
    await state.clear()
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔄 Добавить еще", callback_data=f"m_addslot_{date}"))
    kb.row(InlineKeyboardButton(text="📅 Вернуться к дате", callback_data="m_calendar"))
    await message.answer(
        f"✅ Слот {date} {st[0]:02d}:{st[1]:02d}-{en[0]:02d}:{en[1]:02d} добавлен.",
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data.startswith("m_clear_"))
async def m_clear(callback: CallbackQuery):
    date = callback.data.split("_")[2]
    db.clear_free_slots_for_date(callback.from_user.id, date)
    await _render_day(callback.message, callback.from_user.id, date)


@router.callback_query(F.data.startswith("m_del_"))
async def m_delete_single_slot(callback: CallbackQuery):
    _, _, slot_id, date = callback.data.split("_", 3)
    deleted = db.delete_free_slot_by_id(callback.from_user.id, int(slot_id))
    if not deleted:
        await callback.answer("Нельзя удалить: слот занят или уже удален.", show_alert=True)
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
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🏠 В меню", callback_data="m_main"))
    await message.answer("✅ Фото прайса сохранено.", reply_markup=kb.as_markup())


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
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🏠 В меню", callback_data="m_main"))
    await message.answer("✅ Профиль услуг обновлен.", reply_markup=kb.as_markup())


@router.message(Command("skip"), MasterStates.waiting_photo)
async def m_skip_photo(message: Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🏠 В меню", callback_data="m_main"))
    await message.answer("✅ Профиль услуг обновлен без фото.", reply_markup=kb.as_markup())


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
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🏠 В меню", callback_data="m_main"))
    await message.answer("✅ Ссылка сохранена.", reply_markup=kb.as_markup())


@router.callback_query(F.data == "m_subscription_info")
async def m_subscription_info(callback: CallbackQuery):
    _, days_left = subscription_service.check_access(callback.from_user.id)
    ref_stats = db.get_referral_stats(callback.from_user.id)
    text = (
        "💎 <b>Подписка</b>\n\n"
        f"Осталось дней: <b>{days_left}</b>\n\n"
        f"🏆 Бонусов: <b>{ref_stats['bonus_points']}</b>\n"
        "Конвертация: 12 бонусов = 1 сутки продления.\n\n"
        "Для продления подписки напишите:\n"
        "<a href='https://t.me/ivan8954'>@ivan8954</a>"
    )
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🎁 Потратить 12 бонусов (1 сутки)", callback_data="m_redeem_bonus_1"))
    kb.row(InlineKeyboardButton(text="Написать @ivan8954", url="https://t.me/ivan8954"))
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="m_main"))
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())


@router.callback_query(F.data == "m_redeem_bonus_1")
async def m_redeem_bonus_1(callback: CallbackQuery):
    ok = db.spend_master_bonus_points(callback.from_user.id, 12)
    if not ok:
        return await callback.answer("Недостаточно бонусов.", show_alert=True)
    subscription_service.activate(callback.from_user.id, 1)
    await callback.answer("✅ Продлено на 1 сутки за 12 бонусов.", show_alert=True)
    await m_subscription_info(callback)


@router.callback_query(F.data == "m_referral")
async def m_referral(callback: CallbackQuery):
    me = await callback.bot.get_me()
    ref_link = f"https://t.me/{me.username}?start=ref_{callback.from_user.id}"
    stats = db.get_referral_stats(callback.from_user.id)
    text = (
        "🎁 <b>Реферальная система</b>\n\n"
        "Приглашайте новых мастеров вашей ссылкой.\n"
        "За каждого активированного мастера +100 бонусов.\n\n"
        f"Ваши приглашения: <b>{stats['count']}</b>\n"
        f"Бонусы по реферальной программе: <b>{stats['bonus_points']}</b>\n\n"
        f"Ссылка:\n<code>{ref_link}</code>"
    )
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="m_main"))
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())


@router.callback_query(F.data == "m_profile")
async def m_profile(callback: CallbackQuery):
    access, days_left = subscription_service.check_access(callback.from_user.id)
    if not access:
        return await callback.message.edit_text("Подписка закончилась.")
    p = db.get_master_profile_stats(callback.from_user.id)
    text = (
        "👤 <b>Профиль мастера</b>\n\n"
        f"💎 Подписка: <b>{days_left} дн.</b>\n"
        f"👥 Всего клиентов: <b>{p['total_clients']}</b>\n"
        f"📅 Активных записей: <b>{p['active_bookings']}</b>\n"
        f"⭐ Рейтинг: <b>{p['rating']}</b>\n"
        f"🎁 Приглашено мастеров: <b>{p['referrals']}</b>\n"
        f"🏆 Реферальные бонусы: <b>{p['referral_bonus_points']}</b>"
    )
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="m_main"))
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())


@router.callback_query(F.data == "m_feedback_menu")
async def m_feedback_menu(callback: CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💡 Предложение", callback_data="feedback_suggestion"))
    kb.row(InlineKeyboardButton(text="🐞 Сообщить об ошибке", callback_data="feedback_bug"))
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="m_main"))
    await callback.message.edit_text("Что хотите отправить владельцу?", reply_markup=kb.as_markup())


@router.callback_query(F.data == "m_crm_clients")
async def m_crm_clients(callback: CallbackQuery):
    rows = db.list_master_clients(callback.from_user.id, limit=40)
    if not rows:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="m_main"))
        return await callback.message.edit_text("🧾 Клиентов пока нет.", reply_markup=kb.as_markup())
    text = "🧾 <b>Клиенты (Mini-CRM)</b>\n\nВыберите клиента:"
    kb = InlineKeyboardBuilder()
    for row in rows:
        label = f"{row['display']} | {row['visits']} виз."
        kb.button(text=label[:60], callback_data=f"m_crm_{row['user_id']}")
    kb.adjust(1)
    kb.button(text="⬅️ Назад", callback_data="m_main")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("m_crm_"))
async def m_crm_card(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[-1])
    card = db.get_client_card(callback.from_user.id, user_id)
    p = card["profile"]
    display = (p["first_name"] if p else None) or (p["username"] if p else None) or str(user_id)
    note = card["note"] or "—"
    text = (
        "👤 <b>Карточка клиента</b>\n\n"
        f"ID: <code>{user_id}</code>\n"
        f"Имя: <b>{display}</b>\n"
        f"Визитов: <b>{card['visits']}</b>\n"
        f"Активных записей: <b>{card['active_bookings']}</b>\n\n"
        f"Заметка:\n{note}"
    )
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✍️ Изменить заметку", callback_data=f"m_crm_note_{user_id}"))
    kb.row(InlineKeyboardButton(text="⬅️ К клиентам", callback_data="m_crm_clients"))
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("m_crm_note_"))
async def m_crm_note_start(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[-1])
    await state.set_state(MasterStates.waiting_crm_note)
    await state.update_data(crm_user_id=user_id)
    await callback.message.edit_text("Введите заметку для клиента одним сообщением.")


@router.message(MasterStates.waiting_crm_note)
async def m_crm_note_save(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = int(data.get("crm_user_id"))
    db.set_client_note(message.from_user.id, user_id, message.text or "")
    await state.clear()
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🏠 В меню", callback_data="m_main"))
    await message.answer("✅ Заметка сохранена.", reply_markup=kb.as_markup())
