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
    builder.row(InlineKeyboardButton(text="📸 Ссылка на портфолио", callback_data="admin_portfolio_start"))
    builder.row(InlineKeyboardButton(text="🏠 В главное меню", callback_data="to_main"))
    builder.adjust(1)
    return builder.as_markup()

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID: 
        return
    await message.answer("🛠 <b>Панель администратора</b>", parse_mode="HTML", reply_markup=admin_kb())

# --- УПРАВЛЕНИЕ ССЫЛКОЙ ---
@router.callback_query(F.data == "admin_portfolio_start")
async def admin_portfolio_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Пришлите ссылку на портфолио (http...):", 
                                     reply_markup=InlineKeyboardBuilder().row(InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin_back")).as_markup())
    await state.set_state(AdminStates.waiting_portfolio)

@router.message(AdminStates.waiting_portfolio)
async def admin_portfolio_save(message: Message, state: FSMContext):
    if not message.text.startswith("http"):
        return await message.answer("❌ Ссылка должна начинаться с http.")
    db.update_portfolio(message.text)
    await message.answer("✅ Сохранено!", reply_markup=admin_kb())
    await state.clear()

# --- УПРАВЛЕНИЕ СЛОТАМИ ---
@router.callback_query(F.data == "admin_calendar")
async def admin_cal(callback: CallbackQuery):
    now = datetime.now()
    await callback.message.edit_text("Выберите дату:", reply_markup=generate_calendar(now.year, now.month, is_admin=True))

@router.callback_query(F.data.startswith("admin_date_"))
async def admin_edit_day(callback: CallbackQuery):
    date = callback.data.split("_")[2]
    slots = db.get_admin_slots(date)
    text = f"Дата: <b>{date}</b>\n\nСлоты:\n"
    for s_id, s_time, booked in slots:
        text += f"{'🔴' if booked else '🟢'} {s_time}\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚡ Авто (10:00-19:00)", callback_data=f"auto_{date}"))
    builder.row(InlineKeyboardButton(text="🗑 Удаление", callback_data=f"clear_menu_{date}"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_calendar"))
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.adjust(1).as_markup())

@router.callback_query(F.data.startswith("auto_"))
async def auto_fill(callback: CallbackQuery):
    date = callback.data.split("_")[1]
    for t in ["10:00", "11:30", "13:00", "14:30", "16:00", "17:30", "19:00"]:
        db.add_slot(date, t)
    await admin_edit_day(callback)

@router.callback_query(F.data.startswith("clear_menu_"))
async def admin_clear_menu(callback: CallbackQuery):
    date = callback.data.split("_")[2]
    db.delete_all_slots_on_date(date)
    await admin_edit_day(callback)

# --- НАСТРОЙКА УСЛУГ (4 ШАГА С ФОТО) ---
@router.callback_query(F.data == "admin_services_start")
async def admin_services_main(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    msg = await callback.message.answer("<b>Шаг 1/4: Основные услуги</b>\nВведите текст:")
    await state.update_data(last_msg=msg.message_id)
    await state.set_state(ServiceStates.waiting_main)

@router.message(ServiceStates.waiting_main)
async def admin_services_step2(message: Message, state: FSMContext):
    db.update_services("main_services", message.text)
    await message.delete()
    data = await state.get_data()
    try: await message.bot.delete_message(message.chat.id, data['last_msg'])
    except: pass
    msg = await message.answer("<b>Шаг 2/4: Доп. услуги</b>\nПришлите текст:")
    await state.update_data(last_msg=msg.message_id)
    await state.set_state(ServiceStates.waiting_additional)

@router.message(ServiceStates.waiting_additional)
async def admin_services_step3(message: Message, state: FSMContext):
    db.update_services("additional_services", message.text)
    await message.delete()
    data = await state.get_data()
    try: await message.bot.delete_message(message.chat.id, data['last_msg'])
    except: pass
    msg = await message.answer("<b>Шаг 3/4: Гарантия</b>\nПришлите текст:")
    await state.update_data(last_msg=msg.message_id)
    await state.set_state(ServiceStates.waiting_warranty)

@router.message(ServiceStates.waiting_warranty)
async def admin_services_step4(message: Message, state: FSMContext):
    db.update_services("warranty", message.text)
    await message.delete()
    data = await state.get_data()
    try: await message.bot.delete_message(message.chat.id, data['last_msg'])
    except: pass
    msg = await message.answer(
        "<b>Шаг 4/4: Фото услуг</b>\nПришлите фото или нажмите /skip:", 
        reply_markup=InlineKeyboardBuilder().row(InlineKeyboardButton(text="⏩ Пропустить", callback_data="skip_photo")).as_markup()
    )
    await state.update_data(last_msg=msg.message_id)
    await state.set_state(ServiceStates.waiting_photo)

@router.message(ServiceStates.waiting_photo, F.photo)
@router.callback_query(F.data == "skip_photo")
async def admin_services_finish(event, state: FSMContext):
    data = await state.get_data()
    chat_id = event.chat.id if isinstance(event, Message) else event.message.chat.id
    if isinstance(event, Message):
        db.update_services("photo_id", event.photo[-1].file_id)
        await event.delete()
    
    try: await event.bot.delete_message(chat_id, data['last_msg'])
    except: pass
    await event.bot.send_message(chat_id, "✅ Услуги и фото обновлены!", reply_markup=admin_kb())
    await state.clear()