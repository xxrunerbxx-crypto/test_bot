import asyncio
import re
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
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

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def validate_phone(phone: str) -> str | None:
    """Очистка и проверка номера телефона"""
    digits = re.sub(r'\D', '', phone)
    if digits.startswith('8') and len(digits) == 11:
        digits = '7' + digits[1:]
    elif len(digits) == 10:
        digits = '7' + digits
    
    if len(digits) == 11 and digits.startswith('7'):
        return f"+{digits}"
    return None

# --- ГЛАВНОЕ МЕНЮ ---

@router.message(Command("start"))
@router.callback_query(F.data == "to_main")
async def main_menu(event, state: FSMContext = None):
    if state: 
        await state.clear()
    
    portfolio_url = db.get_portfolio_link()
    text = "💅 <b>Привет! Я бот для записи на маникюр.</b>\n\nВыберите действие ниже:"
    kb = inline.main_menu(portfolio_url)
    
    if isinstance(event, Message):
        await event.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        try:
            await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except:
            # Если сообщение нельзя редактировать (например, оно старое), отправляем новое
            await event.message.answer(text, reply_markup=kb, parse_mode="HTML")

# --- ПРОСМОТР УСЛУГ ---

@router.callback_query(F.data == "services")
async def show_services(callback: CallbackQuery):
    services = db.get_services()
    if not services:
        return await callback.answer("❌ Услуги еще не настроены мастером.", show_alert=True)
    
    main, additional, warranty = services
    text = (
        f"<b>💅 ОСНОВНЫЕ УСЛУГИ:</b>\n{main}\n\n"
        f"<b>✨ ДОП. УСЛУГИ:</b>\n{additional}\n\n"
        f"<b>🛡 ГАРАНТИЯ:</b>\n{warranty}"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=inline.back_kb())

# --- ПРОЦЕСС ЗАПИСИ (FSM) ---

@router.callback_query(F.data == "start_booking")
async def show_calendar(callback: CallbackQuery):
    """Шаг 1: Выбор даты в календаре"""
    now = datetime.now()
    await callback.message.edit_text(
        "📅 <b>Выберите дату для записи:</b>\n\n<i>Кнопки с числами — свободные дни. Прочерки — занято.</i>",
        parse_mode="HTML",
        reply_markup=generate_calendar(now.year, now.month)
    )

@router.callback_query(F.data.startswith("user_date_"))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    """Шаг 2: Выбор времени"""
    date = callback.data.split("_")[2]
    await state.update_data(date=date)
    
    # Получаем слоты из БД
    slots = await asyncio.to_thread(db.get_available_slots, date)
    
    if not slots:
        return await callback.answer("❌ Извините, на эту дату все слоты уже заняты.", show_alert=True)
    
    builder = InlineKeyboardBuilder()
    for s_id, s_time in slots:
        builder.add(InlineKeyboardButton(text=s_time, callback_data=f"slot_{s_id}_{s_time}"))
    
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="start_booking"))
    builder.row(InlineKeyboardButton(text="🏠 В меню", callback_data="to_main"))
    
    await callback.message.edit_text(f"⏰ <b>Выбрана дата: {date}</b>\nТеперь выберите время:", 
                                     parse_mode="HTML", 
                                     reply_markup=builder.as_markup())
    await state.set_state(BookingStates.choosing_time)

@router.callback_query(BookingStates.choosing_time, F.data.startswith("slot_"))
async def ask_name(callback: CallbackQuery, state: FSMContext):
    """Шаг 3: Ввод имени"""
    data = callback.data.split("_")
    await state.update_data(slot_id=data[1], time=data[2])
    
    await callback.message.edit_text("👤 <b>Введите ваше Имя и Фамилию:</b>\n\n<i>Это нужно мастеру для записи.</i>", 
                                     parse_mode="HTML")
    await state.set_state(BookingStates.entering_name)

@router.message(BookingStates.entering_name)
async def ask_phone(message: Message, state: FSMContext):
    """Шаг 4: Ввод телефона"""
    await state.update_data(name=message.text)
    
    await message.answer(
        "📞 <b>Последний шаг!</b>\n\nНажмите кнопку ниже, чтобы отправить номер автоматически, или введите его вручную (+7...):",
        parse_mode="HTML",
        reply_markup=inline.phone_kb()
    )
    await state.set_state(BookingStates.entering_phone)

@router.message(BookingStates.entering_phone)
async def finish_booking(message: Message, state: FSMContext, bot: Bot):
    """Шаг 5: Сохранение записи"""
    data = await state.get_data()
    
    # Обработка телефона
    if message.contact:
        phone = message.contact.phone_number
        if not phone.startswith('+'): phone = f"+{phone}"
    else:
        phone = validate_phone(message.text)
        if not phone:
            return await message.answer("❌ <b>Ошибка в номере!</b>\nВведите корректный номер (11 цифр) или нажмите кнопку ниже:")

    user = message.from_user
    username = f"@{user.username}" if user.username else f"<a href='tg://user?id={user.id}'>Ссылка</a>"
    
    # 1. Добавляем напоминание в планировщик
    job_id = schedule_reminder(bot, user.id, data['date'], data['time'])
    
    # 2. Сохраняем в БД
    await asyncio.to_thread(
        db.create_booking, 
        user.id, data['slot_id'], data['name'], phone, f"{data['date']} {data['time']}", str(job_id)
    )
    
    # 3. Уведомление пользователю
    portfolio_url = db.get_portfolio_link()
    await message.answer(
        f"✅ <b>Запись успешно создана!</b>\n\n📅 Дата: {data['date']}\n⏰ Время: {data['time']}\n\n"
        f"<i>За день до визита я пришлю вам напоминание.</i>", 
        parse_mode="HTML", 
        reply_markup=inline.main_menu(portfolio_url)
    )
    
    # 4. Уведомление админу и в канал
    admin_msg = (
        f"🆕 <b>НОВАЯ ЗАПИСЬ!</b>\n\n"
        f"👤 <b>Клиент:</b> {data['name']}\n"
        f"📞 <b>Тел:</b> <code>{phone}</code>\n"
        f"📱 <b>Юзер:</b> {username}\n"
        f"📅 <b>Когда:</b> {data['date']} в {data['time']}"
    )
    
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="HTML")
        if CHANNEL_ID:
            await bot.send_message(chat_id=CHANNEL_ID, text=admin_msg, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка при отправке уведомления админу: {e}")
    
    await state.clear()

# --- ОТМЕНА ЗАПИСИ ---

@router.callback_query(F.data == "cancel_booking")
async def cancel_booking_handler(callback: CallbackQuery):
    # Метод возвращает job_id напоминания, если запись была
    job_id = db.cancel_booking(callback.from_user.id)
    
    if job_id:
        await callback.answer("✅ Ваша запись успешно отменена.", show_alert=True)
        # Возвращаем в главное меню
        await main_menu(callback)
    else:
        await callback.answer("❌ У вас нет активных записей для отмены.", show_alert=True)