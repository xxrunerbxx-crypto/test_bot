import asyncio
import re
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import db
from keyboards import inline
from keyboards.calendar_kb import generate_calendar
from utils.states import BookingStates
from utils.scheduler import schedule_reminder, schedule_feedback # Импортируем опрос
from datetime import datetime

router = Router()

def validate_phone(phone: str) -> str | None:
    digits = re.sub(r'\D', '', phone)
    if digits.startswith('8') and len(digits) == 11:
        digits = '7' + digits[1:]
    elif len(digits) == 10:
        digits = '7' + digits
    if len(digits) == 11 and digits.startswith('7'):
        return f"+{digits}"
    return None

@router.message(Command("start"))
async def main_menu(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    args = command.args

    # Логируем пользователя, который начал пользоваться ботом (/start).
    # Это нужно для админ-панели и рассылок.
    try:
        db.upsert_user_on_start(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
    except Exception:
        # Не ломаем вход в бот из-за проблем со справочником пользователей.
        pass
    
    # Если зашли по ссылке /start 12345 (ID мастера)
    if args and args.isdigit():
        master_id = int(args)
        await state.update_data(master_id=master_id)
        
        portfolio_url = db.get_portfolio_link(master_id)
        text = "💅 <b>Привет! Вы записываетесь к нашему специалисту.</b>\n\nВыберите действие ниже:"
        # Передаем master_id в меню для работы Web App и ссылок
        kb = inline.main_menu(portfolio_url, master_id)
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        # Если зашли без параметров
        await message.answer("Добро пожаловать! Если вы мастер и хотите настроить бота для своих клиентов — используйте команду /admin.")

@router.callback_query(F.data == "to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    master_id = data.get('master_id')
    
    if not master_id:
        return await callback.answer("Ошибка: данные мастера потеряны. Перезайдите по ссылке мастера.")
    
    portfolio_url = db.get_portfolio_link(master_id)
    try: await callback.message.delete()
    except: pass
    
    await callback.message.answer(
        "💅 <b>Выберите действие ниже:</b>", 
        reply_markup=inline.main_menu(portfolio_url, master_id), 
        parse_mode="HTML"
    )

@router.callback_query(F.data == "services")
async def show_services(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    master_id = data.get('master_id')
    
    if not master_id:
        return await callback.answer("Ошибка: мастер не найден.")

    services = db.get_services(master_id)
    if not services:
        return await callback.answer("❌ Услуги еще не настроены мастером.", show_alert=True)
    
    main, add, war, photo_id = services
    text = (
        f"<b>💅 ОСНОВНЫЕ УСЛУГИ:</b>\n{main}\n\n"
        f"<b>✨ ДОП. УСЛУГИ:</b>\n{add}\n\n"
        f"<b>🛡 ГАРАНТИЯ:</b>\n{war}"
    )
    
    await callback.message.delete()
    if photo_id and photo_id != "None":
        await callback.message.answer_photo(
            photo=photo_id, caption=text, 
            parse_mode="HTML", reply_markup=inline.back_kb()
        )
    else:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=inline.back_kb())

@router.callback_query(F.data == "start_booking")
async def show_calendar(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    master_id = data.get('master_id')

    # ПРОВЕРКА ПОДПИСКИ МАСТЕРА
    access, _ = db.check_master_access(master_id)
    if not access:
        return await callback.answer(
            "❌ Извините, запись к этому мастеру временно закрыта (истек срок подписки).",
            show_alert=True,
        )

    # Блокируем запись во время техработ
    maintenance = db.get_maintenance()
    if maintenance.get("enabled"):
        msg = maintenance.get("message") or "Сервис временно недоступен"
        return await callback.answer(f"🛠 {msg}", show_alert=True)

    now = datetime.now()
    await callback.message.edit_text(
        "📅 <b>Выберите дату для записи:</b>",
        parse_mode="HTML",
        reply_markup=generate_calendar(now.year, now.month, master_id=master_id),
    )

@router.callback_query(F.data.startswith("user_date_"))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    date = callback.data.split("_")[2]
    await state.update_data(date=date)
    data = await state.get_data()
    
    slots = db.get_available_slots(data['master_id'], date)
    if not slots:
        return await callback.answer("❌ Извините, на этот день мест больше нет.", show_alert=True)
    
    builder = InlineKeyboardBuilder()
    for s_id, s_time in slots:
        builder.button(text=s_time, callback_data=f"slot_{s_id}_{s_time}")
    
    builder.adjust(3).row(inline.InlineKeyboardButton(text="⬅️ Назад к датам", callback_data="start_booking"))
    
    await callback.message.edit_text(
        f"⏰ Доступное время на <b>{date}</b>:", 
        parse_mode="HTML", 
        reply_markup=builder.as_markup()
    )
    await state.set_state(BookingStates.choosing_time)

@router.callback_query(BookingStates.choosing_time, F.data.startswith("slot_"))
async def ask_name(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split("_")
    await state.update_data(slot_id=data[1], time=data[2])
    await callback.message.edit_text("👤 Введите ваше <b>Имя и Фамилию</b>:", parse_mode="HTML")
    await state.set_state(BookingStates.entering_name)

@router.message(BookingStates.entering_name)
async def ask_phone(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📞 Отправьте ваш номер телефона для связи:", reply_markup=inline.phone_kb())
    await state.set_state(BookingStates.entering_phone)

@router.message(BookingStates.entering_phone)
async def finish_booking(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    phone = message.contact.phone_number if message.contact else validate_phone(message.text)
    
    if not phone:
        return await message.answer("❌ Пожалуйста, введите корректный номер телефона.")

    # Блокируем запись во время техработ
    maintenance = db.get_maintenance()
    if maintenance.get("enabled"):
        msg = maintenance.get("message") or "Сервис временно недоступен"
        return await message.answer(f"🛠 {msg}")

    try:
        # 1. Атомарно резервируем слот (чтобы избежать двойного бронирования)
        booking_id = db.create_booking(
            data['master_id'], 
            message.from_user.id, 
            data['slot_id'], 
            data['name'], 
            phone, 
            f"{data['date']} {data['time']}", 
            "no_reminder",
        )

        # 2. Планируем напоминание за 24 часа (только после успешного резервирования)
        reminder_job_id = schedule_reminder(bot, message.from_user.id, data['date'], data['time'])

        # 3. Планируем опрос о качестве (через 2-3 часа после записи)
        schedule_feedback(bot, message.from_user.id, data['master_id'], data['date'], data['time'])

        # 4. Сохраняем job_id reminder в бронь
        if reminder_job_id:
            db.set_booking_job_id(booking_id, str(reminder_job_id))

        portfolio_url = db.get_portfolio_link(data['master_id'])
        await message.answer(
            f"✅ <b>Запись успешно подтверждена!</b>\n\n📅 Дата: {data['date']}\n⏰ Время: {data['time']}\n\nБудем ждать вас! ❤️", 
            parse_mode="HTML", 
            reply_markup=inline.main_menu(portfolio_url, data['master_id'])
        )

        # 4. Уведомляем МАСТЕРА
        admin_msg = (
            f"🆕 <b>НОВАЯ ЗАПИСЬ!</b>\n\n"
            f"👤 Клиент: {data['name']}\n"
            f"📞 Тел: <code>{phone}</code>\n"
            f"📅 Дата: {data['date']}\n"
            f"⏰ Время: {data['time']}"
        )
        await bot.send_message(data['master_id'], admin_msg, parse_mode="HTML")
        
        await state.clear()
    except Exception as e:
        await message.answer("❌ Произошла ошибка при сохранении записи. Пожалуйста, попробуйте позже.")

# ПУНКТ 3: ОБРАБОТЧИК ЗВЕЗД (ОТЗЫВОВ)
@router.callback_query(F.data.startswith("rate_"))
async def rating_handler(callback: CallbackQuery):
    _, master_id, rating = callback.data.split("_")
    db.save_review(int(master_id), callback.from_user.id, int(rating))
    await callback.message.edit_text("❤️ <b>Спасибо за вашу оценку!</b>\nМы рады, что вы выбрали нас.")

@router.callback_query(F.data == "cancel_booking")
async def cancel_booking_handler(callback: CallbackQuery, state: FSMContext):
    job_id, master_id = db.cancel_booking(callback.from_user.id)
    if master_id:
        # Уведомляем мастера об отмене
        await callback.bot.send_message(master_id, "⚠️ <b>Внимание!</b>\nОдин из клиентов отменил свою запись.")
        await callback.answer("✅ Ваша запись отменена.", show_alert=True)
        
        # Обновляем меню
        portfolio_url = db.get_portfolio_link(master_id)
        await callback.message.edit_text(
            "💅 Выберите действие ниже:", 
            reply_markup=inline.main_menu(portfolio_url, master_id)
        )
    else:
        await callback.answer("❌ У вас нет активных записей.", show_alert=True)