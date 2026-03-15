import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_ID, CHANNEL_ID, CHANNEL_LINK
from database.db import db
from keyboards import inline
from keyboards.calendar_kb import generate_calendar
from utils.states import BookingStates
from utils.scheduler import schedule_reminder, scheduler
from datetime import datetime

router = Router()

async def is_subscribed(bot: Bot, user_id: int):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

@router.message(Command("start"))
@router.callback_query(F.data == "to_main")
async def main_menu(event, state: FSMContext = None):
    if state: await state.clear()
    
    # Ссылка берется из КЭША БД мгновенно
    portfolio_url = db.get_portfolio_link()
    
    text = "💅 Привет! Я бот для записи на маникюр.\nВыберите действие ниже:"
    kb = inline.main_menu(portfolio_url)
    
    if isinstance(event, Message):
        await event.answer(text, reply_markup=kb)
    else:
        await event.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data == "services")
async def show_services(callback: CallbackQuery):
    # Берем из КЭША мгновенно
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
    # ПРОВЕРКА ПОДПИСКИ (сетевой запрос, может занять время)
    if not await is_subscribed(bot, callback.from_user.id):
        await callback.answer("Подпишитесь на наш канал!", show_alert=False)
    
    # Работа с БД в отдельном потоке
    has_book = await asyncio.to_thread(db.has_booking, callback.from_user.id)
    if has_book:
        return await callback.answer("У вас уже есть активная запись!", show_alert=True)

    now = datetime.now()
    # Генерация календаря тоже может дергать БД, поэтому в поток (если generate_calendar обращается к db)
    kb = await asyncio.to_thread(generate_calendar, now.year, now.month, False)
    
    await callback.message.edit_text("📅 Выберите дату:", reply_markup=kb)

@router.callback_query(F.data.startswith("user_date_"))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    date = callback.data.split("_")[2]
    await state.update_data(date=date)
    
    # В ПОТОКЕ (ЧТЕНИЕ С ДИСКА)
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
    await callback.message.edit_text("👤 Введите ваше <b>Имя и Фамилию</b>:", reply_markup=builder.as_markup())
    await state.set_state(BookingStates.entering_name)

@router.message(BookingStates.entering_name)
async def ask_phone(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    builder = InlineKeyboardBuilder().row(InlineKeyboardButton(text="🏠 Отмена", callback_data="to_main"))
    await message.answer("📞 Введите <b>номер телефона</b>:", reply_markup=builder.as_markup())
    await state.set_state(BookingStates.entering_phone)

@router.message(BookingStates.entering_phone)
async def finish_booking(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    phone = message.text
    
    job_id = schedule_reminder(bot, message.from_user.id, data['date'], data['time'])
    
    # ЗАПИСЬ В БД В ПОТОКЕ
    await asyncio.to_thread(db.create_booking, message.from_user.id, data['slot_id'], data['name'], phone, f"{data['date']} {data['time']}", str(job_id))
    
    url = db.get_portfolio_link()
    await message.answer(f"✅ <b>Запись создана!</b>\n\n📅 {data['date']} в {data['time']}", reply_markup=inline.main_menu(url))
    
    msg = f"🆕 <b>Новая запись!</b>\n\n👤 {data['name']}\n📞 {phone}\n📅 {data['date']} в {data['time']}"
    await bot.send_message(ADMIN_ID, msg)
    await bot.send_message(CHANNEL_ID, msg)
    await state.clear()

@router.callback_query(F.data == "cancel_booking")
async def cancel_handler(callback: CallbackQuery):
    # ОТМЕНА В ПОТОКЕ
    job_id = await asyncio.to_thread(db.cancel_booking, callback.from_user.id)
    if job_id:
        try: scheduler.remove_job(job_id)
        except: pass
        await callback.answer("✅ Запись отменена", show_alert=True)
    else:
        await callback.answer("У вас нет активных записей", show_alert=True)