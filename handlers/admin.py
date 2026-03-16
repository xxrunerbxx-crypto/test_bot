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
    """Главное меню админа"""
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

# --- УПРАВЛЕНИЕ ССЫЛКОЙ НА ПОРТФОЛИО ---

@router.callback_query(F.data == "admin_portfolio_start")
async def admin_portfolio_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 <b>Настройка портфолио</b>\n\nПришлите ссылку на ваше портфолио (Instagram, TG или сайт).\n\n"
        "<i>Ссылка должна начинаться с http:// или https://</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin_back")
        ).as_markup()
    )
    await state.set_state(AdminStates.waiting_portfolio)

@router.message(AdminStates.waiting_portfolio)
async def admin_portfolio_save(message: Message, state: FSMContext):
    link = message.text.strip()
    if not link.startswith("http"):
        return await message.answer("❌ <b>Ошибка!</b>\nСсылка должна начинаться с http. Попробуйте еще раз:")
    
    db.update_portfolio(link)
    await message.answer(f"✅ <b>Ссылка успешно сохранена!</b>\n{link}", 
                         parse_mode="HTML", reply_markup=admin_kb())
    await state.clear()

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🛠 <b>Панель администратора</b>", parse_mode="HTML", reply_markup=admin_kb())

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
    if not slots: 
        text += "<i>Слотов нет</i>"
    for s_id, s_time, booked in slots:
        status = "🔴 (Занято)" if booked else "🟢 (Свободно)"
        text += f"{status} {s_time}\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚡ Стандарт (10, 13, 16, 19)", callback_data=f"auto_{date}"))
    builder.row(InlineKeyboardButton(text="➕ Свой слот", callback_data=f"manual_{date}"))
    builder.row(InlineKeyboardButton(text="🗑 Удаление слотов", callback_data=f"clear_menu_{date}"))
    builder.row(InlineKeyboardButton(text="⬅️ К календарю", callback_data="admin_calendar"))
    builder.adjust(1)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("clear_menu_"))
async def admin_clear_menu(callback: CallbackQuery):
    date = callback.data.split("_")[2]
    slots = db.get_admin_slots(date)
    builder = InlineKeyboardBuilder()
    for s_id, s_time, booked in slots:
        status = "🔴" if booked else "🟢"
        builder.add(InlineKeyboardButton(text=f"Удалить {status} {s_time}", callback_data=f"delslot_{s_id}_{date}"))
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔥 УДАЛИТЬ ВСЁ НА ЭТУ ДАТУ", callback_data=f"delall_{date}"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_date_{date}"))
    await callback.message.edit_text(f"Удаление слотов на {date}:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("delslot_"))
async def admin_delete_single_slot(callback: CallbackQuery):
    data = callback.data.split("_")
    db.delete_slot_by_id(data[1])
    await admin_clear_menu(callback)

@router.callback_query(F.data.startswith("delall_"))
async def admin_delete_all_day(callback: CallbackQuery):
    date = callback.data.split("_")[1]
    db.delete_all_slots_on_date(date)
    await admin_edit_day(callback)

@router.callback_query(F.data.startswith("auto_"))
async def auto_fill(callback: CallbackQuery):
    date = callback.data.split("_")[1]
    for t in ["10:00", "13:00", "16:00", "19:00"]:
        db.add_slot(date, t)
    await admin_edit_day(callback)

@router.callback_query(F.data.startswith("manual_"))
async def manual_slot(callback: CallbackQuery, state: FSMContext):
    date = callback.data.split("_")[1]
    await state.update_data(admin_date=date)
    await callback.message.answer(f"Введите время для {date} (в формате 15:30):")
    await state.set_state(AdminStates.adding_time)

@router.message(AdminStates.adding_time)
async def save_manual_slot(message: Message, state: FSMContext):
    data = await state.get_data()
    db.add_slot(data['admin_date'], message.text)
    await message.answer(f"✅ Время {message.text} добавлено!", reply_markup=admin_kb())
    await state.clear()

# --- НАСТРОЙКА УСЛУГ (ПОШАГОВАЯ) ---

@router.callback_query(F.data == "admin_services_start")
async def admin_services_main(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    msg = await callback.message.answer("<b>Шаг 1/3: Основные услуги</b>\nВведите список услуг и цен одним сообщением:")
    await state.update_data(last_msg=msg.message_id)
    await state.set_state(ServiceStates.waiting_main)

@router.message(ServiceStates.waiting_main)
async def admin_services_step2(message: Message, state: FSMContext):
    db.update_services("main_services", message.text)
    data = await state.get_data()
    try: await message.bot.delete_message(message.chat.id, data['last_msg'])
    except: pass
    await message.delete()
    msg = await message.answer("<b>Шаг 2/3: Дополнительные услуги</b>\nПришлите текст:")
    await state.update_data(last_msg=msg.message_id)
    await state.set_state(ServiceStates.waiting_additional)

@router.message(ServiceStates.waiting_additional)
async def admin_services_step3(message: Message, state: FSMContext):
    db.update_services("additional_services", message.text)
    data = await state.get_data()
    try: await message.bot.delete_message(message.chat.id, data['last_msg'])
    except: pass
    await message.delete()
    msg = await message.answer("<b>Шаг 3/3: Гарантия и информация</b>\nПришлите текст или нажмите /skip:", 
                               reply_markup=InlineKeyboardBuilder().row(InlineKeyboardButton(text="⏩ Пропустить", callback_data="skip_warranty")).as_markup())
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