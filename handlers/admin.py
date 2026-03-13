import re
import asyncio
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

import config
from database import db
import keyboards as kb
from states import AdminStates

router = Router()

@router.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    if message.from_user.id != config.ADMIN_ID: return
    saved_pass = await db.get_admin_password()
    if not saved_pass:
        await message.answer("👋 Первый запуск! Придумайте пароль:")
        await state.set_state(AdminStates.waiting_for_new_password)
    else:
        await message.answer("🔐 Введите пароль администратора:")
        await state.set_state(AdminStates.waiting_for_password)

@router.message(AdminStates.waiting_for_new_password)
async def create_pass(message: types.Message, state: FSMContext):
    await db.set_admin_password(message.text)
    await message.delete()
    await message.answer("✅ Пароль установлен! Введите его для входа:")
    await state.set_state(AdminStates.waiting_for_password)

@router.message(AdminStates.waiting_for_password)
async def check_pass(message: types.Message, state: FSMContext):
    saved_pass = await db.get_admin_password()
    if message.text == saved_pass:
        await message.delete()
        await state.clear()
        await message.answer("🛠 Панель мастера:", reply_markup=kb.admin_menu())
    else:
        await message.answer("❌ Неверно! Попробуйте снова:")

# --- ДОБАВЛЕНИЕ СЛОТОВ ---
@router.callback_query(F.data == "admin_add_slot")
async def add_slot_start(callback: types.CallbackQuery, state: FSMContext):
    now = datetime.now()
    calendar_kb = await kb.generate_calendar(now.month, now.year, [], is_admin=True)
    await callback.message.edit_text("Выберите дату:", reply_markup=calendar_kb)
    await state.set_state(AdminStates.adding_slot_date)

@router.callback_query(AdminStates.adding_slot_date)
async def admin_date_sel(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "ignore": return
    date = callback.data.split("_")[1]
    await state.update_data(date=date)
    await callback.message.edit_text(f"📅 Дата: {date}\nВведите время (напр: 10:00 12:00) или шаблон:", reply_markup=kb.admin_time_templates())
    await state.set_state(AdminStates.adding_slot_time)

@router.callback_query(AdminStates.adding_slot_time, F.data.startswith("tpl_"))
async def admin_tpl(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tpls = {"tpl_morning": ["09:00", "11:00", "13:00"], "tpl_afternoon": ["14:00", "16:00", "18:00"], "tpl_evening": ["19:00", "21:00"], "tpl_fullday": ["09:00", "12:00", "15:00", "18:00"]}
    for t in tpls.get(callback.data): await db.add_slot(data['date'], t)
    await callback.message.answer(f"✅ Добавлено на {data['date']}", reply_markup=kb.admin_menu())
    await state.clear()

@router.message(AdminStates.adding_slot_time)
async def admin_multi_t(message: types.Message, state: FSMContext):
    data = await state.get_data()
    times = re.findall(r"\d{1,2}:\d{2}", message.text)
    for t in times: await db.add_slot(data['date'], t)
    await message.answer(f"✅ Добавлено: {', '.join(times)}", reply_markup=kb.admin_menu())
    await state.clear()

# --- УСЛУГИ ---
@router.callback_query(F.data == "admin_setup_services")
async def setup_services(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📜 Шаг 1: Основные услуги (название - цена):")
    await state.set_state(AdminStates.filling_main_services)

@router.message(AdminStates.filling_main_services)
async def step2(message: types.Message, state: FSMContext):
    await db.update_service_block('main_services', message.text)
    await message.answer("➕ Шаг 2: Доп. услуги:")
    await state.set_state(AdminStates.filling_add_services)

@router.message(AdminStates.filling_add_services)
async def step3(message: types.Message, state: FSMContext):
    await db.update_service_block('add_services', message.text)
    await message.answer("🛡 Шаг 3: Гарантия:")
    await state.set_state(AdminStates.filling_warranty)

@router.message(AdminStates.filling_warranty)
async def step_fin(message: types.Message, state: FSMContext):
    await db.update_service_block('warranty', message.text)
    await message.answer("✅ Услуги обновлены!", reply_markup=kb.admin_menu())
    await state.clear()

# --- РАССЫЛКА И УДАЛЕНИЕ ---
@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📢 Текст рассылки:")
    await state.set_state(AdminStates.broadcast_message)

@router.message(AdminStates.broadcast_message)
async def broadcast_send(message: types.Message, state: FSMContext):
    users = await db.get_all_users()
    for u in users:
        try: await message.copy_to(u); await asyncio.sleep(0.05)
        except: pass
    await message.answer("✅ Рассылка завершена!", reply_markup=kb.admin_menu())
    await state.clear()

@router.callback_query(F.data == "admin_delete_slots")
async def del_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите дату для удаления слотов (12.01):")
    await state.set_state(AdminStates.deleting_slot_date)

@router.message(AdminStates.deleting_slot_date)
async def del_step2(message: types.Message, state: FSMContext):
    slots = await db.get_slots_by_date(message.text)
    builder = InlineKeyboardBuilder()
    for s_id, s_time in slots: builder.row(InlineKeyboardButton(text=f"Удалить {s_time}", callback_data=f"del_{s_id}"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_menu"))
    await message.answer(f"Выберите слот на {message.text}:", reply_markup=builder.as_markup())
    await state.clear()

@router.callback_query(F.data.startswith("del_"))
async def del_fin(callback: types.CallbackQuery):
    await db.delete_slot(callback.data.split("_")[1])
    await callback.message.edit_text("✅ Удалено!", reply_markup=kb.admin_menu())

@router.callback_query(F.data == "admin_view_schedule")
async def view_sch(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите дату (12.01):")
    await state.set_state(AdminStates.view_schedule_date)

@router.message(AdminStates.view_schedule_date)
async def view_res(message: types.Message, state: FSMContext):
    res = await db.get_admin_schedule(message.text)
    if not res: await message.answer("Нет записей.")
    else:
        txt = f"📅 {message.text}:\n\n"
        for b in res: txt += f"⏰ {b['time']} - {b['user_name']} ({b['user_phone']})\n"
        await message.answer(txt, reply_markup=kb.admin_menu())
    await state.clear()

@router.callback_query(F.data == "admin_set_portfolio")
async def set_port(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Ссылка на портфолио:")
    await state.set_state(AdminStates.setting_portfolio)

@router.message(AdminStates.setting_portfolio)
async def port_res(message: types.Message, state: FSMContext):
    await db.set_portfolio(message.text)
    await message.answer("✅ Сохранено!", reply_markup=kb.admin_menu())
    await state.clear()