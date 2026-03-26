from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import db
from config import ADMIN_ID, PAYMENT_TOKEN # Обязательно добавь PAYMENT_TOKEN в config.py
from utils.states import AdminStates, ServiceStates
from keyboards.calendar_kb import generate_calendar
from datetime import datetime
from aiogram.exceptions import TelegramForbiddenError

router = Router()

# --- SUPER-ADMIN MENU (единое меню для ADMIN_ID) ---

def super_admin_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users_0"))
    builder.row(InlineKeyboardButton(text="👤 Мастера и подписки", callback_data="admin_masters_0"))
    builder.row(InlineKeyboardButton(text="🗂 Клиенты и записи", callback_data="admin_bookings_0"))
    builder.row(InlineKeyboardButton(text="📣 Рассылка всем", callback_data="admin_broadcast_start"))
    builder.row(InlineKeyboardButton(text="🛠 Техработы", callback_data="admin_maintenance_menu"))
    builder.row(InlineKeyboardButton(text="⬅️ В главное меню", callback_data="admin_main_menu"))
    builder.adjust(1)
    return builder.as_markup()


async def render_admin_main(message_or_callback):
    # сообщение может быть Message или CallbackQuery
    if hasattr(message_or_callback, "from_user"):
        user_id = message_or_callback.from_user.id
    else:
        user_id = message_or_callback.message.from_user.id

    if user_id != ADMIN_ID:
        return

    maintenance = db.get_maintenance()
    users_count = db.count_users()
    masters_count = db.cur.execute("SELECT COUNT(*) FROM masters_info").fetchone()[0]
    bookings_count = db.count_bookings()

    text = (
        "🛠 <b>Главная админ-панель</b>\n\n"
        f"👥 Пользователи: <b>{users_count}</b>\n"
        f"👤 Мастера: <b>{masters_count}</b>\n"
        f"🗂 Записи: <b>{bookings_count}</b>\n\n"
        f"🛠 Техработы: <b>{'ВКЛ' if maintenance.get('enabled') else 'ВЫКЛ'}</b>\n"
        f"<i>{maintenance.get('message') or ''}</i>\n"
    )

    kb = super_admin_menu()
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message_or_callback.answer(text, parse_mode="HTML", reply_markup=kb)


# Основная клавиатура админки
def admin_kb(days_left: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📅 Управление слотами", callback_data="admin_calendar"))
    builder.row(InlineKeyboardButton(text="📊 Моя статистика", callback_data="admin_stats"))
    builder.row(InlineKeyboardButton(text="⚙️ Настройка услуг", callback_data="admin_services_start"))
    builder.row(InlineKeyboardButton(text="📸 Ссылка на портфолио", callback_data="admin_portfolio_start"))
    builder.row(InlineKeyboardButton(text=f"💎 Подписка ({days_left} дн.)", callback_data="admin_subscription"))
    builder.row(InlineKeyboardButton(text="🏠 В главное меню", callback_data="to_main"))
    builder.adjust(1)
    return builder.as_markup()

# --- КОМАНДА ДЛЯ ТЕБЯ (СУПЕР-АДМИНА) ---
# Формат: /activate 1234567 30
@router.message(Command("activate"))
async def activate_manual(message: Message):
    if message.from_user.id != ADMIN_ID:
        return # Игнорируем, если пишет не хозяин бота
    
    try:
        args = message.text.split()
        target_id = int(args[1])
        days = int(args[2])
        
        new_date = db.set_subscription(target_id, days)
        await message.answer(f"✅ Мастер <code>{target_id}</code> активирован!\nНовая дата окончания: <b>{new_date}</b>", parse_mode="HTML")
        
        # Уведомляем мастера о продлении
        await message.bot.send_message(target_id, f"🎉 <b>Подписка продлена!</b>\nВаш доступ активен до: {new_date}\n\nСпасибо, что выбрали наш сервис! ❤️", parse_mode="HTML")
    except Exception as e:
        await message.answer("❌ Ошибка! Формат: <code>/activate [ID_мастера] [кол-во_дней]</code>", parse_mode="HTML")

# --- ВХОД В АДМИНКУ ---
@router.message(Command("admin"))
async def admin_panel(message: Message):
    # SUPER-ADMIN MENU
    if message.from_user.id == ADMIN_ID:
        await render_admin_main(message)
        return

    master_id = message.from_user.id
    access, days_left = db.check_master_access(master_id)
    
    if not access:
        # Если срок истек, показываем только кнопку оплаты
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="💎 Продлить подписку", callback_data="admin_subscription"))
        return await message.answer(
            "⚠️ <b>Ваш доступ истек!</b>\n\nПробный период (7 дней) завершен. Пожалуйста, продлите подписку, чтобы продолжить принимать записи клиентов.",
            parse_mode="HTML", reply_markup=kb.as_markup()
        )

    # Если доступ есть
    me = await message.bot.get_me()
    link = f"https://t.me/{me.username}?start={master_id}"
    
    text = (f"🛠 <b>Панель мастера</b>\n"
            f"Статус: 🟢 Активен (осталось {days_left} дн.)\n\n"
            f"Ваша ссылка для записи клиентов:\n"
            f"<code>{link}</code>")
    await message.answer(text, parse_mode="HTML", reply_markup=admin_kb(days_left))

# --- NAVIGATION: admin_main_menu ---
@router.callback_query(F.data == "admin_main_menu")
async def admin_main_menu(callback: CallbackQuery):
    await render_admin_main(callback)

# --- USERS LIST ---
@router.callback_query(F.data.startswith("admin_users_"))
async def admin_users(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Недостаточно прав.", show_alert=True)

    try:
        offset = int(callback.data.split("_")[-1])
    except Exception:
        offset = 0

    limit = 20
    total = db.count_users()
    users = db.list_users(limit=limit, offset=offset)

    if not users:
        text = "👥 Пользователей пока нет."
    else:
        lines = []
        for user_id, username, first_name, started_at, last_seen in users:
            display = first_name or username or "—"
            last = (last_seen or "").split(" ")[0] if last_seen else "—"
            lines.append(f"• <code>{user_id}</code>: {display} (с {started_at.split(' ')[0] if started_at else '—'}) [свеж. {last}]")
        text = f"👥 Пользователи (показано {len(users)} из {total}):\n\n" + "\n".join(lines)

    builder = InlineKeyboardBuilder()
    if offset > 0:
        prev_offset = max(0, offset - limit)
        builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_users_{prev_offset}"))
    if offset + limit < total:
        next_offset = offset + limit
        builder.row(InlineKeyboardButton(text="➡️ Дальше", callback_data=f"admin_users_{next_offset}"))
    builder.row(InlineKeyboardButton(text="⬅️ В главное меню", callback_data="admin_main_menu"))

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())

# --- MASTERS LIST / SUBSCRIPTION ---
@router.callback_query(F.data == "admin_masters_0")
async def admin_masters(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Недостаточно прав.", show_alert=True)

    masters = db.list_masters()
    if not masters:
        text = "👤 Мастеров пока нет."
    else:
        lines = []
        for master_id, subscription_until in masters[:50]:
            try:
                days_left = (datetime.strptime(subscription_until, "%Y-%m-%d") - datetime.now()).days
                status = f"{days_left} дн." if days_left >= 0 else "истекло"
            except Exception:
                status = "—"
            lines.append(f"• <code>{master_id}</code>: до <b>{subscription_until}</b> ({status})")
        text = "👤 Мастера и подписки:\n\n" + "\n".join(lines)
        if len(masters) > 50:
            text += "\n\n(показано первые 50)"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Продлить подписку (master_id days)", callback_data="admin_subscribe_manual"))
    builder.row(InlineKeyboardButton(text="⬅️ В главное меню", callback_data="admin_main_menu"))

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())

# --- Manual subscription extend flow ---
@router.callback_query(F.data == "admin_subscribe_manual")
async def admin_subscribe_manual(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Недостаточно прав.", show_alert=True)
    await state.clear()
    await state.set_state(AdminStates.waiting_subscription_input)
    await callback.message.edit_text(
        "Введите данные в формате:\n\n`master_id days`\n\nПример: `123456 30`",
        parse_mode="Markdown"
    )

@router.message(AdminStates.waiting_subscription_input)
async def admin_subscription_input(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        return await message.answer("❌ Неверный формат. Пример: `123456 30`", parse_mode="Markdown")

    try:
        master_id = int(parts[0])
        days = int(parts[1])
    except Exception:
        return await message.answer("❌ master_id и days должны быть числами.", parse_mode="Markdown")

    new_date = db.set_subscription(master_id, days)
    await message.answer(
        f"✅ Подписка мастера <code>{master_id}</code> продлена на <b>{days}</b> дней.\nНовая дата окончания: <b>{new_date}</b>",
        parse_mode="HTML"
    )
    await state.clear()
    await render_admin_main(message)

# --- BOOKINGS LIST ---
@router.callback_query(F.data.startswith("admin_bookings_"))
async def admin_bookings(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Недостаточно прав.", show_alert=True)

    try:
        offset = int(callback.data.split("_")[-1])
    except Exception:
        offset = 0

    limit = 20
    total = db.count_bookings()
    bookings = db.list_bookings(limit=limit, offset=offset)

    if not bookings:
        text = "🗂 Записей пока нет."
    else:
        lines = []
        for b_id, master_id, user_id, name, phone, date_time, job_id in bookings:
            display = name or "—"
            dt = (date_time or "").split(" ")[0] + " " + (date_time or "").split(" ")[1] if date_time and " " in date_time else (date_time or "—")
            lines.append(
                f"• Запись <code>{b_id}</code> / мастер <code>{master_id}</code> / клиент <code>{user_id}</code>\n"
                f"  {display} — <code>{phone}</code>\n"
                f"  {dt}"
            )
        text = f"🗂 Записи клиентов (показано {len(bookings)} из {total}):\n\n" + "\n".join(lines)

    builder = InlineKeyboardBuilder()
    if offset > 0:
        prev_offset = max(0, offset - limit)
        builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_bookings_{prev_offset}"))
    if offset + limit < total:
        next_offset = offset + limit
        builder.row(InlineKeyboardButton(text="➡️ Дальше", callback_data=f"admin_bookings_{next_offset}"))
    builder.row(InlineKeyboardButton(text="⬅️ В главное меню", callback_data="admin_main_menu"))

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())

# --- MAINTENANCE MENU ---
@router.callback_query(F.data == "admin_maintenance_menu")
async def admin_maintenance_menu(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Недостаточно прав.", show_alert=True)

    maintenance = db.get_maintenance()
    enabled = maintenance.get("enabled")
    msg = maintenance.get("message") or ""
    updated_at = maintenance.get("updated_at") or "—"

    enabled_text = "ВКЛ" if enabled else "ВЫКЛ"
    text = (
        "🛠 Техработы\n\n"
        f"Сейчас: <b>{enabled_text}</b>\n"
        f"Сообщение: <i>{msg}</i>\n"
        f"Обновлено: <code>{updated_at}</code>\n"
    )

    builder = InlineKeyboardBuilder()
    if enabled:
        builder.row(InlineKeyboardButton(text="⚪️ Выключить техработы", callback_data="admin_maintenance_off"))
    else:
        builder.row(InlineKeyboardButton(text="🟢 Включить техработы", callback_data="admin_maintenance_on"))
    builder.row(InlineKeyboardButton(text="⬅️ В главное меню", callback_data="admin_main_menu"))

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())

@router.callback_query(F.data == "admin_maintenance_on")
async def admin_maintenance_on(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Недостаточно прав.", show_alert=True)
    db.set_maintenance(True)
    # Рассылаем всем пользователям текст из настройки техработ
    try:
        maintenance = db.get_maintenance()
        msg = maintenance.get("message") or "Сервис временно недоступен"
        user_ids = db.get_all_user_ids()
        sent = 0
        failed = 0
        for uid in user_ids:
            try:
                await callback.bot.send_message(uid, msg)
                sent += 1
            except Exception:
                failed += 1
        # (не показываем детали пользователям, просто обновляем меню)
    except Exception:
        pass

    await admin_maintenance_menu(callback)

@router.callback_query(F.data == "admin_maintenance_off")
async def admin_maintenance_off(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Недостаточно прав.", show_alert=True)
    db.set_maintenance(False)
    await admin_maintenance_menu(callback)


# --- BROADCAST TO ALL USERS ---
@router.callback_query(F.data == "admin_broadcast_start")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Недостаточно прав.", show_alert=True)
    await state.clear()
    await state.set_state(AdminStates.waiting_broadcast_text)
    await callback.message.edit_text(
        "📣 Введите текст рассылки всем пользователям.\n\n"
        "Поддерживаются HTML теги.\n"
        "Пример:\n"
        "<b>Важно!</b>\n\nПишем обновление."
    )


@router.message(AdminStates.waiting_broadcast_text)
async def admin_broadcast_text(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    text = message.text or ""
    if not text.strip():
        return await message.answer("Текст рассылки не может быть пустым.")

    await state.update_data(broadcast_text=text)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Отправить всем", callback_data="admin_broadcast_confirm"))
    kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcast_cancel"))
    await state.set_state(AdminStates.waiting_broadcast_confirm)
    await message.answer("Нажмите подтверждение, чтобы отправить сообщение всем пользователям.", reply_markup=kb.as_markup())


@router.callback_query(F.data == "admin_broadcast_cancel")
async def admin_broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Недостаточно прав.", show_alert=True)
    await state.clear()
    await render_admin_main(callback)


@router.callback_query(F.data == "admin_broadcast_confirm")
async def admin_broadcast_confirm(callback: CallbackQuery, state: FSMContext, bot: any):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Недостаточно прав.", show_alert=True)
    data = await state.get_data()
    text = (data.get("broadcast_text") or "").strip()
    if not text:
        await state.clear()
        return await callback.message.answer("❌ Текст рассылки не найден. Запустите заново.")

    user_ids = db.get_all_user_ids()
    total = len(user_ids)
    sent = 0
    failed = 0
    errors = []

    # Отправляем последовательно, чтобы не упереться в rate-limit.
    for uid in user_ids:
        try:
            await callback.bot.send_message(uid, text, parse_mode="HTML")
            sent += 1
        except TelegramForbiddenError as e:
            failed += 1
            if len(errors) < 10:
                errors.append((uid, str(e)))
        except Exception as e:
            failed += 1
            if len(errors) < 10:
                errors.append((uid, str(e)))

    await state.clear()
    summary = (
        "📣 Рассылка завершена.\n\n"
        f"Всего: <b>{total}</b>\n"
        f"Отправлено: <b>{sent}</b>\n"
        f"Ошибок: <b>{failed}</b>\n"
    )
    if errors:
        summary += "\nПервые ошибки:\n" + "\n".join([f"• <code>{uid}</code>: {err}" for uid, err in errors])

    await callback.message.edit_text(summary, parse_mode="HTML", reply_markup=super_admin_menu())

# --- ЛОГИКА ОПЛАТЫ (ДЛЯ ЗАЯВКИ В КАССУ) ---

@router.callback_query(F.data == "admin_subscription")
async def send_payment_invoice(callback: CallbackQuery):
    # Проверка: если токен не настроен
    if not PAYMENT_TOKEN or PAYMENT_TOKEN == "ТОКЕН":
        return await callback.message.answer("❌ Автоматическая оплата временно недоступна.\nДля продления напишите администратору: @твой_логин")

    await callback.message.bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Подписка на 30 дней",
        description="Доступ к функциям записи клиентов и управлению слотами.",
        payload="month_sub",
        provider_token=PAYMENT_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label="Подписка на бота", amount=50000)], # 500 рублей
        start_parameter="sub_pay"
    )

@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    # Обязательный ответ Телеграму, что мы готовы принять деньги
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment)
async def got_payment(message: Message):
    # Вызывается автоматически после успешного списания денег
    db.set_subscription(message.from_user.id, 30)
    await message.answer(
        "✅ <b>Оплата прошла успешно!</b>\nВаша подписка продлена на 30 дней. Удачи в делах! ❤️",
        parse_mode="HTML"
    )

# --- ОСТАЛЬНЫЕ ОБРАБОТЧИКИ (СТАТИСТИКА, СЛОТЫ, УСЛУГИ) ---

@router.callback_query(F.data == "admin_stats")
async def show_stats(callback: CallbackQuery):
    stats = db.get_master_stats(callback.from_user.id)
    text = (
        f"📊 <b>Ваша статистика:</b>\n\n"
        f"👥 Всего клиентов: <b>{stats['total']}</b>\n"
        f"📅 Активных записей: <b>{stats['active']}</b>\n"
        f"⭐ Ваш рейтинг: <b>{stats['rating']}</b>"
    )
    kb = InlineKeyboardBuilder().row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back_to_menu")).as_markup()
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "admin_back_to_menu")
async def back_to_admin(callback: CallbackQuery):
    # При возврате назад снова проверяем доступ
    await admin_panel(callback.message)
    await callback.message.delete()

@router.callback_query(F.data == "admin_calendar")
async def admin_cal(callback: CallbackQuery):
    now = datetime.now()
    await callback.message.edit_text("Выберите дату:", 
        reply_markup=generate_calendar(now.year, now.month, master_id=callback.from_user.id, is_admin=True))

@router.callback_query(F.data.startswith("admin_date_"))
async def admin_edit_day(callback: CallbackQuery):
    date = callback.data.split("_")[2]
    slots = db.get_admin_slots(callback.from_user.id, date)
    
    text = f"Дата: <b>{date}</b>\n\n"
    for s_id, s_time, booked in slots:
        status = "🔴" if booked else "🟢"
        text += f"{status} {s_time}\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚡ Авто (10:00-19:00)", callback_data=f"auto_{date}"))
    builder.row(InlineKeyboardButton(text="🗑 Очистить день", callback_data=f"clear_menu_{date}"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_calendar"))
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.adjust(1).as_markup())

@router.callback_query(F.data.startswith("auto_"))
async def auto_fill(callback: CallbackQuery):
    date = callback.data.split("_")[1]
    for t in ["10:00", "11:30", "13:00", "14:30", "16:00", "17:30", "19:00"]:
        db.add_slot(callback.from_user.id, date, t)
    await admin_edit_day(callback)

@router.callback_query(F.data.startswith("clear_menu_"))
async def admin_clear_menu(callback: CallbackQuery):
    date = callback.data.split("_")[2]
    db.delete_all_slots_on_date(callback.from_user.id, date)
    await admin_edit_day(callback)

# --- НАСТРОЙКА УСЛУГ ---
@router.callback_query(F.data == "admin_services_start")
async def admin_services_step1(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    msg = await callback.message.answer("<b>Шаг 1/4: Основные услуги</b>\nВведите список услуг и цены:")
    await state.update_data(last_msg=msg.message_id)
    await state.set_state(ServiceStates.waiting_main)

@router.message(ServiceStates.waiting_main)
async def admin_services_step2(message: Message, state: FSMContext):
    db.update_services(message.from_user.id, "main_services", message.text)
    data = await state.get_data()
    try: await message.bot.delete_message(message.chat.id, data['last_msg'])
    except: pass
    msg = await message.answer("<b>Шаг 2/4: Доп. услуги</b>\nВведите доп. услуги или 'Нет':")
    await state.update_data(last_msg=msg.message_id)
    await state.set_state(ServiceStates.waiting_additional)

@router.message(ServiceStates.waiting_additional)
async def admin_services_step3(message: Message, state: FSMContext):
    db.update_services(message.from_user.id, "additional_services", message.text)
    data = await state.get_data()
    try: await message.bot.delete_message(message.chat.id, data['last_msg'])
    except: pass
    msg = await message.answer("<b>Шаг 3/4: Гарантия</b>\nУсловия возврата или гарантии:")
    await state.update_data(last_msg=msg.message_id)
    await state.set_state(ServiceStates.waiting_warranty)

@router.message(ServiceStates.waiting_warranty)
async def admin_services_step4(message: Message, state: FSMContext):
    db.update_services(message.from_user.id, "warranty", message.text)
    data = await state.get_data()
    try: await message.bot.delete_message(message.chat.id, data['last_msg'])
    except: pass
    msg = await message.answer("<b>Шаг 4/4: Фото</b>\nПришлите фото или /skip:", reply_markup=InlineKeyboardBuilder().row(InlineKeyboardButton(text="⏩ Пропустить", callback_data="skip_photo")).as_markup())
    await state.update_data(last_msg=msg.message_id)
    await state.set_state(ServiceStates.waiting_photo)

@router.message(ServiceStates.waiting_photo, F.photo)
@router.callback_query(F.data == "skip_photo")
async def admin_services_finish(event, state: FSMContext):
    data = await state.get_data()
    user_id = event.from_user.id
    if isinstance(event, Message):
        db.update_services(user_id, "photo_id", event.photo[-1].file_id)
        chat_id = event.chat.id
    else:
        chat_id = event.message.chat.id
    try: await event.bot.delete_message(chat_id, data['last_msg'])
    except: pass
    await event.bot.send_message(chat_id, "✅ Профиль обновлен!", reply_markup=admin_kb("..."))
    await state.clear()

# --- ПОРТФОЛИО ---
@router.callback_query(F.data == "admin_portfolio_start")
async def admin_portfolio_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Пришлите ссылку на портфолио:", reply_markup=InlineKeyboardBuilder().row(InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin_back_to_menu")).as_markup())
    await state.set_state(AdminStates.waiting_portfolio)

@router.message(AdminStates.waiting_portfolio)
async def admin_portfolio_save(message: Message, state: FSMContext):
    if not message.text.startswith("http"):
        return await message.answer("❌ Ссылка должна начинаться с http.")
    db.update_portfolio(message.from_user.id, message.text)
    await message.answer("✅ Сохранено!", reply_markup=admin_kb("..."))
    await state.clear()