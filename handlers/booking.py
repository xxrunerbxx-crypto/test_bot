import re
from datetime import datetime
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

import config
from database import db
import keyboards as kb
from states import BookingStates

router = Router()

# ========================================================================
# УСЛУГИ, ПОРТФОЛИО И МОЯ ЗАПИСЬ (ПРОСМОТР)
# ========================================================================
@router.callback_query(F.data == "show_services")
async def show_services(callback: types.CallbackQuery):
    """Показывает все три блока услуг одним сообщением"""
    blocks = await db.get_service_blocks()
    if not blocks:
        await callback.answer("Информация об услугах еще не заполнена.", show_alert=True)
        return
    
    full_message = (
        "<b>✨ НАШИ УСЛУГИ И ЦЕНЫ ✨</b>\n\n"
        "<b>💅 Основные услуги:</b>\n"
        f"<i>{blocks.get('main_services', 'Не заполнено')}</i>\n\n"
        "<b>➕ Дополнительно:</b>\n"
        f"<i>{blocks.get('add_services', 'Не заполнено')}</i>\n\n"
        "<b>🛡 Гарантия:</b>\n"
        f"<i>{blocks.get('warranty', 'Не заполнено')}</i>"
    )
    await callback.message.edit_text(full_message, reply_markup=kb.back_to_main())

@router.callback_query(F.data == "show_portfolio")
async def show_portfolio(callback: types.CallbackQuery):
    link = await db.get_portfolio()
    if link:
        kb_port = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="👀 Смотреть работы", url=link)],
            [types.InlineKeyboardButton(text="🔙 Назад", callback_data="to_main")]
        ])
        await callback.message.edit_text("Моё портфолио доступно по ссылке: 👇", reply_markup=kb_port)
    else:
        await callback.message.edit_text("Портфолио пока не заполнено.", reply_markup=kb.back_to_main())

@router.callback_query(F.data == "my_booking")
async def my_booking(callback: types.CallbackQuery):
    """Позволяет клиенту увидеть свою запись и отменить её"""
    booking = await db.get_user_booking(callback.from_user.id)
    if booking:
        text = (f"<b>Ваша запись:</b>\n\n"
                f"📅 Дата: {booking['date']}\n"
                f"⏰ Время: {booking['time']}\n"
                f"👤 Имя: {booking['user_name']}\n"
                f"📞 Тел: {booking['user_phone']}")
        
        cancel_kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Отменить запись", callback_data="cancel_booking")],
            [types.InlineKeyboardButton(text="🔙 Назад", callback_data="to_main")]
        ])
        await callback.message.edit_text(text, reply_markup=cancel_kb)
    else:
        await callback.message.edit_text("У вас нет активных записей.", reply_markup=kb.back_to_main())

@router.callback_query(F.data == "cancel_booking")
async def cancel_booking(callback: types.CallbackQuery):
    await db.cancel_booking(callback.from_user.id)
    await callback.message.edit_text("✅ <b>Запись успешно отменена.</b>", reply_markup=kb.main_menu())
    await callback.bot.send_message(config.ADMIN_ID, f"⚠️ <b>Отмена!</b> Клиент @{callback.from_user.username} отменил запись.")

# ========================================================================
# ПРОЦЕСС ЗАПИСИ (КАЛЕНДАРЬ -> ВРЕМЯ -> ФИО -> ТЕЛ)
# ========================================================================
@router.callback_query(F.data == "start_booking")
async def booking_calendar(callback: types.CallbackQuery, state: FSMContext):
    if await db.user_has_booking(callback.from_user.id):
        await callback.answer("У вас уже есть запись!", show_alert=True)
        return

    dates = await db.get_available_dates()
    now = datetime.now()
    calendar_markup = await kb.generate_calendar(now.month, now.year, dates, is_admin=False)
    
    await callback.message.edit_text("📅 <b>Выберите дату для записи:</b>", reply_markup=calendar_markup)
    await state.set_state(BookingStates.choosing_date)

@router.callback_query(BookingStates.choosing_date)
async def booking_time(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "ignore": return
    date = callback.data.split("_")[1]
    await state.update_data(date=date)
    
    times = await db.get_slots_by_date(date)
    if not times:
        await callback.answer("Упс! На эту дату время уже заняли.", show_alert=True)
        return

    inline_kb = [[types.InlineKeyboardButton(text=t[1], callback_data=f"slot_{t[0]}_{t[1]}")] for t in times]
    inline_kb.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="start_booking")])
    
    await callback.message.edit_text(f"📅 <b>Дата: {date}</b>\nВыберите свободное время:", 
                                     reply_markup=types.InlineKeyboardMarkup(inline_keyboard=inline_kb))
    await state.set_state(BookingStates.choosing_time)

@router.callback_query(BookingStates.choosing_time)
async def booking_name(callback: types.CallbackQuery, state: FSMContext):
    slot_id, slot_time = callback.data.split("_")[1], callback.data.split("_")[2]
    await db.lock_slot(slot_id) # Бронь на 2 мин
    await state.update_data(slot_id=slot_id, time=slot_time)
    await callback.message.answer("👤 <b>Введите ваше Имя и Фамилию:</b>")
    await state.set_state(BookingStates.entering_name)

@router.message(BookingStates.entering_name)
async def booking_phone(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📞 <b>Введите ваш номер телефона:</b>\n(Например: +79991234567)")
    await state.set_state(BookingStates.entering_phone)

@router.message(BookingStates.entering_phone)
async def booking_finish(message: types.Message, state: FSMContext):
    if not re.match(r"^\+?\d{10,15}$", message.text):
        await message.answer("❌ <b>Ошибка!</b> Введите номер телефона цифрами.")
        return
    
    data = await state.get_data()
    # Сохранение в БД
    await db.book_slot(data['slot_id'], message.from_user.id, data['name'], message.text)
    
    await message.answer(f"✅ <b>Успешно!</b>\nВы записаны на <b>{data['date']} в {data['time']}</b>.\nЖдем вас! ❤️", reply_markup=kb.main_menu())
    
    # Отчет для мастера и канала
    report = (f"🎉 <b>НОВАЯ ЗАПИСЬ!</b>\n\n📅 <b>Дата:</b> {data['date']}\n⏰ <b>Время:</b> {data['time']}\n"
              f"👤 <b>Клиент:</b> {data['name']}\n📞 <b>Тел:</b> <code>{message.text}</code>")
    
    await message.bot.send_message(config.ADMIN_ID, report)
    if config.LOG_CHANNEL_ID != 0:
        try: await message.bot.send_message(config.LOG_CHANNEL_ID, report)
        except: pass
    
    await state.clear()