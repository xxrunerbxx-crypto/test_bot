from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_ID
from database.db import db
from utils.states import AdminStates
from keyboards.calendar_kb import generate_calendar
from datetime import datetime

router = Router()

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID: return
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📅 Управление слотами", callback_data="admin_calendar"))
    builder.row(InlineKeyboardButton(text="🏠 В главное меню", callback_data="to_main"))
    await message.answer("Панель администратора:", reply_markup=builder.as_markup())

@router.callback_query(F.data == "admin_calendar")
async def admin_cal(callback: CallbackQuery):
    now = datetime.now()
    await callback.message.edit_text("Выберите дату для редактирования:", 
                                     reply_markup=generate_calendar(now.year, now.month, is_admin=True))

@router.callback_query(F.data.startswith("admin_date_"))
async def admin_edit_day(callback: CallbackQuery):
    date = callback.data.split("_")[2]
    slots = db.get_admin_slots(date)
    
    text = f"Дата: <b>{date}</b>\n\nТекущие слоты:\n"
    for s_id, s_time, booked in slots:
        status = "🔴" if booked else "🟢"
        text += f"{status} {s_time} (ID: {s_id})\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚡ Стандарт (10, 13, 16, 19)", callback_data=f"auto_{date}"))
    builder.row(InlineKeyboardButton(text="➕ Свой слот", callback_data=f"manual_{date}"))
    builder.row(InlineKeyboardButton(text="🗑 Очистить день", callback_data=f"clear_{date}"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад к календарю", callback_data="admin_calendar"))
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("auto_"))
async def auto_fill(callback: CallbackQuery):
    date = callback.data.split("_")[1]
    for t in ["10:00", "13:00", "16:00", "19:00"]:
        db.add_slot(date, t)
    await callback.answer("Слоты добавлены!")
    await admin_edit_day(callback)

@router.callback_query(F.data.startswith("clear_"))
async def clear_day(callback: CallbackQuery):
    date = callback.data.split("_")[1]
    db.clear_day(date)
    await callback.answer("Свободные слоты удалены")
    await admin_edit_day(callback)

@router.callback_query(F.data.startswith("manual_"))
async def manual_slot(callback: CallbackQuery, state: FSMContext):
    date = callback.data.split("_")[1]
    await state.update_data(admin_date=date)
    await callback.message.answer(f"Введите время для {date} (например, 11:30):")
    await state.set_state(AdminStates.adding_time)

@router.message(AdminStates.adding_time)
async def save_manual_slot(message: Message, state: FSMContext):
    data = await state.get_data()
    db.add_slot(data['admin_date'], message.text)
    await message.answer(f"✅ Время {message.text} добавлено на {data['admin_date']}")
    await state.clear()