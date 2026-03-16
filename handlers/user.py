import asyncio
import re  # Импортируем для проверки номера
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

# Функция для очистки и проверки номера телефона
def validate_phone(phone: str) -> str | None:
    # Удаляем всё кроме цифр
    digits = re.sub(r'\D', '', phone)
    
    # Если номер начинается с 8, меняем на 7
    if digits.startswith('8') and len(digits) == 11:
        digits = '7' + digits[1:]
    # Если номер без кода страны (10 цифр), добавляем 7
    elif len(digits) == 10:
        digits = '7' + digits
    
    # Проверяем, что в итоге 11 цифр и начинается на 7
    if len(digits) == 11 and digits.startswith('7'):
        return f"+{digits}"
    return None

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

# ... (пропускаем функции services, show_calendar, choose_time, ask_name — они остаются прежними)

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

@router.message(BookingStates.entering_name)
async def ask_phone(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(
        "📞 <b>Шаг завершения:</b>\n\nНажмите кнопку ниже для авто-ввода или введите номер вручную (начиная с +7):",
        parse_mode="HTML",
        reply_markup=inline.phone_kb()
    )
    await state.set_state(BookingStates.entering_phone)

@router.message(BookingStates.entering_phone)
async def finish_booking(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    
    # Обработка номера телефона
    if message.contact:
        # Авто-ввод через кнопку (стандарты ТГ не ограничиваем)
        phone = message.contact.phone_number
        if not phone.startswith('+'): phone = f"+{phone}"
    else:
        # Ручной ввод с проверкой
        phone = validate_phone(message.text)
        if not phone:
            return await message.answer("❌ <b>Ошибка в номере!</b>\nПожалуйста, введите корректный номер (11 цифр) или нажмите кнопку авто-ввода:")

    user = message.from_user
    username = f"@{user.username}" if user.username else f"<a href='tg://user?id={user.id}'>Ссылка</a>"
    
    # Сохранение в БД
    job_id = schedule_reminder(bot, user.id, data['date'], data['time'])
    await asyncio.to_thread(db.create_booking, user.id, data['slot_id'], data['name'], phone, f"{data['date']} {data['time']}", str(job_id))
    
    # Сообщение клиенту
    url = db.get_portfolio_link()
    await message.answer(
        f"✅ <b>Запись успешно создана!</b>\n\n📅 Дата: {data['date']}\n⏰ Время: {data['time']}", 
        parse_mode="HTML", 
        reply_markup=inline.main_menu(url) # Убирает кнопку телефона
    )
    
    # ФОРМИРУЕМ ТЕКСТ ДЛЯ АДМИНА
    admin_msg = (
        f"🆕 <b>НОВАЯ ЗАПИСЬ!</b>\n\n"
        f"👤 <b>Клиент:</b> {data['name']}\n"
        f"📞 <b>Тел:</b> <code>{phone}</code>\n"
        f"📱 <b>Юзернейм:</b> {username}\n"
        f"📅 <b>Когда:</b> {data['date']} в {data['time']}"
    )
    
    # ОТПРАВКА АДМИНУ (проверь, что в config.py ADMIN_ID это число!)
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка отправки админу: {e}")

    # ОТПРАВКА В КАНАЛ
    if CHANNEL_ID:
        try:
            await bot.send_message(chat_id=CHANNEL_ID, text=admin_msg, parse_mode="HTML")
        except Exception as e:
            print(f"Ошибка отправки в канал: {e}")
    
    await state.clear()