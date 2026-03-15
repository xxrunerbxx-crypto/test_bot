from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
import database as db
import keyboards as kb
from states import AdminStates
from datetime import datetime

router = Router()

@router.message(Command("admin"))
async def admin_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🛠 Панель мастера:", reply_markup=kb.get_admin_main_kb())

@router.callback_query(F.data == "adm_main")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🛠 Панель мастера:", reply_markup=kb.get_admin_main_kb())

# --- ДОБАВЛЕНИЕ ---
@router.callback_query(F.data == "adm_add")
async def add_slot_date(callback: CallbackQuery, state: FSMContext):
    now = datetime.now()
    await state.set_state(AdminStates.adding_slot_date)
    await callback.message.edit_text("Выберите дату:", 
        reply_markup=await kb.generate_calendar(now.month, now.year, [], is_admin=True))

@router.callback_query(AdminStates.adding_slot_date, F.data.startswith("date_"))
async def add_slot_time(callback: CallbackQuery, state: FSMContext):
    date = callback.data.replace("date_", "")
    await state.update_data(chosen_date=date)
    await state.set_state(AdminStates.adding_slot_time)
    await callback.message.edit_text(f"Дата: {date}\nВведите время через запятую или выберите шаблон:", 
                                     reply_markup=kb.admin_time_templates())

@router.callback_query(AdminStates.adding_slot_time, F.data.startswith("tpl_"))
async def process_template(callback: CallbackQuery, state: FSMContext):
    times = callback.data.replace("tpl_", "").split(',')
    data = await state.get_data()
    for t in times:
        await db.add_slot(data['chosen_date'], t)
    await state.clear()
    await callback.message.edit_text(f"✅ Добавлено: {', '.join(times)}", reply_markup=kb.get_admin_main_kb())

@router.message(AdminStates.adding_slot_time)
async def process_manual_time(message: Message, state: FSMContext):
    times = [t.strip() for t in message.text.split(',')]
    data = await state.get_data()
    for t in times:
        await db.add_slot(data['chosen_date'], t)
    await state.clear()
    await message.answer(f"✅ Добавлено: {', '.join(times)}", reply_markup=kb.get_admin_main_kb())

# --- УДАЛЕНИЕ ---
@router.callback_query(F.data == "adm_del")
async def del_slots_start(callback: CallbackQuery):
    dates = await db.get_unique_dates()
    if not dates: return await callback.answer("Пусто")
    await callback.message.edit_text("Выберите дату для удаления:", reply_markup=kb.get_admin_delete_dates_kb(dates))

@router.callback_query(F.data.startswith("del_date_"))
async def del_slots_list(callback: CallbackQuery):
    date = callback.data.replace("del_date_", "")
    slots = await db.get_slots_by_date(date)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for s in slots:
        builder.button(text=f"{'🔴' if s[2] else '🟢'} {s[1]}", callback_data=f"conf_del_{s[0]}")
    builder.adjust(3)
    builder.row(kb.InlineKeyboardButton(text="« Назад", callback_data="adm_del"))
    await callback.message.edit_text(f"Слоты на {date}:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("conf_del_"))
async def del_slot_final(callback: CallbackQuery):
    await db.delete_slot(int(callback.data.replace("conf_del_", "")))
    await callback.answer("Удалено")
    await del_slots_start(callback)

# --- РАССЫЛКА, УСЛУГИ, ПОРТФОЛИО ---
@router.callback_query(F.data == "adm_msg")
async def start_msg(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.broadcasting)
    await callback.message.edit_text("📢 Текст рассылки:", reply_markup=kb.get_admin_cancel_kb())

@router.callback_query(F.data == "adm_serv")
async def adm_serv(callback: CallbackQuery):
    await callback.message.edit_text("⚙️ Настройка услуг:", reply_markup=kb.get_admin_cancel_kb())

@router.callback_query(F.data == "adm_port")
async def adm_port(callback: CallbackQuery):
    await callback.message.edit_text("🖼 Настройка портфолио:", reply_markup=kb.get_admin_cancel_kb())