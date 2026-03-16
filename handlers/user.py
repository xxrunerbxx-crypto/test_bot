import asyncio
from sched import scheduler
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_ID, CHANNEL_ID
from database.db import db
from keyboards import inline
from keyboards.calendar_kb import generate_calendar
from utils.states import BookingStates
from utils.scheduler import schedule_reminder
from datetime import datetime

router = Router()

@router.message(Command("start"))
@router.callback_query(F.data == "to_main")
async def main_menu(event, state: FSMContext = None):
    if state: await state.clear()
    portfolio_url = db.get_portfolio_link()
    text = "💅 Привет! Я бот для записи на маникюр.\nВыберите действие ниже:"
    kb = inline.main_menu(portfolio_url)
    
    if isinstance(event, Message):
        await event.answer(text, reply_markup=kb)
    else:
        await event.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data == "services")
async def show_services(callback: CallbackQuery):
    services_data = db.get_services()
    main, add, war = services_data if services_data else ("Не заполнено", "Не заполнено", "Не заполнено")
    text = (f"<b>📋 НАШИ УСЛУГИ</b>\n\n"
            f"<b>🔹 Основные:</b>\n{main}\n\n"
            f"<b>➕ Дополнительно:</b>\n{add}\n\n"
            f"<b>🛡 Гарантия:</b>\n{war}")
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💅 Записаться", callback_data="start_booking"))
    builder.row(InlineKeyboardButton(text="🏠 В меню", callback_data="to_main"))
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())

@router.callback_query(F.data == "start_booking")
async def show_calendar(callback: CallbackQuery, bot: Bot):
    has_book = await asyncio.to_thread(db.has_booking, callback.from_user.id)
    if has_book:
        return await callback.answer("У вас уже есть активная запись!", show_alert=True)
    now = datetime.now()
    kb = await asyncio.to_thread(generate_calendar, now.year, now.month, False)
    await callback.message.edit_text("📅 Выберите дату для записи:", reply_markup=kb)

@router.callback_query(F.data.startswith("user_date_"))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    date = callback.data.split("_")[2]
    await state.update_data(date=date)
    slots = await asyncio.to_thread(db.get_available_slots, date)
    builder = InlineKeyboardBuilder()
    for s_id, s_time in slots:
        builder.add(InlineKeyboardButton(text=s_time, callback_data=f"slot_{s_id}_{s_time}"))
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="start_booking"))
    builder.row(InlineKeyboardButton(text="🏠 В меню", callback_data="to_main"))
    await callback.message.edit_text(f"⏰ Свободное время на {date}:", reply_markup=builder.as_markup())
    await state.set_state(BookingStates.choosing_time)

@router.callback_query(BookingStates.choosing_time, F.data.startswith("slot_"))
async def ask_name(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split("_")
    await state.update_data(slot_id=data[1], time=data[2])
    builder = InlineKeyboardBuilder().row(InlineKeyboardButton(text="🏠 Отмена", callback_data="to_main"))
    await callback.message.edit_text("👤 Введите ваше <b>Имя и Фамилию</b>:", parse_mode="HTML", reply_markup=builder.as_markup())
    await state.set_state(BookingStates.entering_name)

# --- ОБНОВЛЕННАЯ ФУНКЦИЯ ЗАПРОСА ТЕЛЕФОНА ---
@router.message(BookingStates.entering_name)
async def ask_phone(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    # Отправляем кнопку запроса контакта (телефон)
    await message.answer(
        "📞 Для завершения записи нажмите кнопку ниже, чтобы <b>отправить свой номер телефона</b>:",
        parse_mode="HTML",
        reply_markup=inline.phone_kb()
    )
    await state.set_state(BookingStates.entering_phone)

# --- ОБНОВЛЕННАЯ ФУНКЦИЯ ЗАВЕРШЕНИЯ ЗАПИСИ ---
@router.message(BookingStates.entering_phone)
async def finish_booking(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    
    # 1. Получаем телефон (через кнопку или текстом)
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text

    # 2. Формируем ссылку на профиль клиента
    user = message.from_user
    if user.username:
        user_link = f"@{user.username}"
    else:
        # Если юзернейма нет, делаем кликабельное имя через ID
        user_link = f"<a href='tg://user?id={user.id}'>{user.full_name}</a>"
    
    # 3. Сохраняем в базу и планируем напоминание
    job_id = schedule_reminder(bot, user.id, data['date'], data['time'])
    await asyncio.to_thread(db.create_booking, user.id, data['slot_id'], data['name'], phone, f"{data['date']} {data['time']}", str(job_id))
    
    # 4. Ответ пользователю (ReplyKeyboardRemove уберет кнопку телефона)
    url = db.get_portfolio_link()
    await message.answer(
        f"✅ <b>Запись успешно создана!</b>\n\n📅 Дата: {data['date']}\n⏰ Время: {data['time']}", 
        parse_mode="HTML", 
        reply_markup=inline.main_menu(url) # Inline-меню заменит кнопку телефона
    )
    
    # 5. Формируем текст для уведомлений
    msg = (f"🆕 <b>Новая запись!</b>\n\n"
           f"👤 Клиент: {data['name']}\n"
           f"📞 Тел: {phone}\n"
           f"🔗 Профиль: {user_link}\n"
           f"📅 Когда: {data['date']} в {data['time']}")
    
    # 6. Уведомление админу
    try:
        await bot.send_message(ADMIN_ID, msg, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка отправки админу: {e}")

    # 7. Уведомление в КАНАЛ
    if CHANNEL_ID and CHANNEL_ID != 0:
        try:
            await bot.send_message(CHANNEL_ID, msg, parse_mode="HTML")
        except Exception as e:
            print(f"❌ ОШИБКА ОТПРАВКИ В КАНАЛ: {e}")
    
    await state.clear()

@router.callback_query(F.data == "cancel_booking")
async def cancel_handler(callback: CallbackQuery):
    job_id = await asyncio.to_thread(db.cancel_booking, callback.from_user.id)
    if job_id:
        try: scheduler.remove_job(job_id)
        except: pass
        await callback.answer("✅ Запись отменена", show_alert=True)
    else:
        await callback.answer("У вас нет активных записей", show_alert=True)