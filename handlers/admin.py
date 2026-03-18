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

router = Router()

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