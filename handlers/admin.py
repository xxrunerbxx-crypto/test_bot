from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_ID
from database.db import db
from utils.states import AdminStates, ServiceStates
from keyboards.calendar_kb import generate_calendar
from datetime import datetime

router = Router()

def admin_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📅 Управление слотами", callback_data="admin_calendar"))
    builder.row(InlineKeyboardButton(text="⚙️ Настройка услуг", callback_data="admin_services_start"))
    builder.row(InlineKeyboardButton(text="🏠 В главное меню", callback_data="to_main"))
    builder.adjust(1)
    return builder.as_markup()

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("🛠 <b>Панель администратора</b>", parse_mode="HTML", reply_markup=admin_kb())

# --- УПРАВЛЕНИЕ СЛОТАМИ ---

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
        text += f"{status} {s_time}\n"
    
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
async def clear_day_handler(callback: CallbackQuery):
    date = callback.data.split("_")[1]
    db.clear_day(date)
    await callback.answer("Свободные слоты удалены")
    await admin_edit_day(callback)

@router.callback_query(F.data.startswith("manual_"))
async def manual_slot(callback: CallbackQuery, state: FSMContext):
    date = callback.data.split("_")[1]
    await state.update_data(admin_date=date)
    await callback.message.answer(f"Введите время для {date} (напр: 11:30):")
    await state.set_state(AdminStates.adding_time)

@router.message(AdminStates.adding_time)
async def save_manual_slot(message: Message, state: FSMContext):
    data = await state.get_data()
    db.add_slot(data['admin_date'], message.text)
    await message.answer(f"✅ Время {message.text} добавлено на {data['admin_date']}", reply_markup=admin_kb())
    await state.clear()

# --- НАСТРОЙКА УСЛУГ (С ОЧИСТКОЙ СООБЩЕНИЙ) ---

@router.callback_query(F.data == "admin_services_start")
async def admin_services_main(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    msg = await callback.message.answer(
        "<b>Шаг 1/3: Основные услуги</b>\n\nПришлите текст с основными услугами и ценами.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardBuilder().row(InlineKeyboardButton(text="🏠 В меню", callback_data="to_main")).as_markup()
    )
    await state.update_data(last_msg=msg.message_id)
    await state.set_state(ServiceStates.waiting_main)

@router.message(ServiceStates.waiting_main)
async def admin_services_step2(message: Message, state: FSMContext):
    db.update_services("main_services", message.text)
    data = await state.get_data()
    await message.bot.delete_message(message.chat.id, data['last_msg'])
    await message.delete()
    
    msg = await message.answer(
        "<b>Шаг 2/3: Дополнительные услуги</b>\n\nПришлите текст с доп. услугами.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardBuilder().row(InlineKeyboardButton(text="🏠 В меню", callback_data="to_main")).as_markup()
    )
    await state.update_data(last_msg=msg.message_id)
    await state.set_state(ServiceStates.waiting_additional)

@router.message(ServiceStates.waiting_additional)
async def admin_services_step3(message: Message, state: FSMContext):
    db.update_services("additional_services", message.text)
    data = await state.get_data()
    await message.bot.delete_message(message.chat.id, data['last_msg'])
    await message.delete()
    
    msg = await message.answer(
        "<b>Шаг 3/3: Гарантия</b>\n\nПришлите текст о гарантии или нажмите кнопку 'Пропустить'.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="⏩ Пропустить", callback_data="skip_warranty"),
            InlineKeyboardButton(text="🏠 В меню", callback_data="to_main")
        ).as_markup()
    )
    await state.update_data(last_msg=msg.message_id)
    await state.set_state(ServiceStates.waiting_warranty)

@router.message(ServiceStates.waiting_warranty)
@router.callback_query(F.data == "skip_warranty")
async def admin_services_finish(event, state: FSMContext):
    data = await state.get_data()
    chat_id = event.chat.id if isinstance(event, Message) else event.message.chat.id
    bot = event.bot if isinstance(event, Message) else event.message.bot

    if isinstance(event, Message):
        db.update_services("warranty", event.text)
        await event.delete()
    
    try: await bot.delete_message(chat_id, data['last_msg'])
    except: pass

    await bot.send_message(chat_id, "✅ <b>Услуги успешно обновлены!</b>", parse_mode="HTML", reply_markup=admin_kb())
    await state.clear()