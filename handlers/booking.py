import re
from datetime import datetime
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

import config
from database import db
import keyboards as kb
from states import BookingStates

router = Router()

@router.callback_query(F.data == "show_services")
async def show_services(callback: types.CallbackQuery):
    blocks = await db.get_service_blocks()
    if not blocks:
        await callback.answer("Услуги еще не заполнены.", show_alert=True)
        return
    txt = (f"<b>✨ УСЛУГИ ✨</b>\n\n<b>💅 Основные:</b>\n{blocks.get('main_services')}\n\n"
           f"<b>➕ Доп:</b>\n{blocks.get('add_services')}\n\n<b>🛡 Гарантия:</b>\n{blocks.get('warranty')}")
    await callback.message.edit_text(txt, reply_markup=kb.back_to_main())

@router.callback_query(F.data == "show_portfolio")
async def show_port(callback: types.CallbackQuery):
    link = await db.get_portfolio()
    if not link: await callback.answer("Портфолио нет.", show_alert=True); return
    k = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="👀 Смотреть", url=link)], [types.InlineKeyboardButton(text="🔙 Назад", callback_data="to_main")]])
    await callback.message.edit_text("Ссылка на работы:", reply_markup=k)

@router.callback_query(F.data == "my_booking")
async def my_book(callback: types.CallbackQuery):
    b = await db.get_user_booking(callback.from_user.id)
    if not b: await callback.message.edit_text("Нет записей.", reply_markup=kb.main_menu()); return
    txt = f"📅 {b['date']}\n⏰ {b['time']}\n👤 {b['user_name']}\n📞 {b['user_phone']}"
    k = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking")], [types.InlineKeyboardButton(text="🔙 Назад", callback_data="to_main")]])
    await callback.message.edit_text(txt, reply_markup=k)

@router.callback_query(F.data == "cancel_booking")
async def cancel_book(callback: types.CallbackQuery):
    await db.cancel_booking(callback.from_user.id)
    await callback.message.edit_text("✅ Отменено.", reply_markup=kb.main_menu())

@router.callback_query(F.data == "start_booking")
async def book_start(callback: types.CallbackQuery, state: FSMContext):
    if await db.user_has_booking(callback.from_user.id): await callback.answer("У вас уже есть запись!", show_alert=True); return
    dates = await db.get_available_dates()
    now = datetime.now()
    calendar_kb = await kb.generate_calendar(now.month, now.year, dates)
    await callback.message.edit_text("Выберите дату:", reply_markup=calendar_kb)
    await state.set_state(BookingStates.choosing_date)

@router.callback_query(BookingStates.choosing_date)
async def book_date(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "ignore": return
    date = callback.data.split("_")[1]
    await state.update_data(date=date)
    times = await db.get_slots_by_date(date)
    k = [[types.InlineKeyboardButton(text=t[1], callback_data=f"slot_{t[0]}_{t[1]}")] for t in times]
    k.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="start_booking")])
    await callback.message.edit_text(f"Выбрано: {date}. Время:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=k))
    await state.set_state(BookingStates.choosing_time)

@router.callback_query(BookingStates.choosing_time)
async def book_time(callback: types.CallbackQuery, state: FSMContext):
    d = callback.data.split("_")
    await db.lock_slot(d[1]); await state.update_data(slot_id=d[1], time=d[2])
    await callback.message.answer("Как вас зовут?")
    await state.set_state(BookingStates.entering_name)

@router.message(BookingStates.entering_name)
async def book_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Телефон (+7...):")
    await state.set_state(BookingStates.entering_phone)

@router.message(BookingStates.entering_phone)
async def book_fin(message: types.Message, state: FSMContext):
    if not re.match(r"^\+?\d{10,15}$", message.text): await message.answer("Неверный формат!"); return
    data = await state.get_data()
    await db.book_slot(data['slot_id'], message.from_user.id, data['name'], message.text)
    await message.answer("✅ Вы записаны!", reply_markup=kb.main_menu())
    await message.bot.send_message(config.ADMIN_ID, f"🎉 Запись!\n{data['name']} {message.text}\n{data['date']} {data['time']}")
    await state.clear()