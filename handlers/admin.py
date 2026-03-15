import re
import asyncio
from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards import get_admin_main_kb, get_admin_delete_dates_kb, admin_time_templates, back_to_main
import database as db
import config
import keyboards as kb
from states import AdminStates

router = Router()

# --- ГЛОБАЛЬНЫЙ ВЫХОД В МЕНЮ ---
@router.callback_query(F.data == "admin_main_menu")
async def back_to_admin_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "👋 Вы вернулись в главное меню администратора.\nВыберите действие:",
        reply_markup=get_admin_main_kb()
    )
    await callback.answer()

# --- УДАЛЕНИЕ ОКОН ЧЕРЕЗ КАЛЕНДАРЬ (РАБОТАЕТ) ---
@router.callback_query(F.data == "admin_delete_slots")
async def process_delete_slots(callback: CallbackQuery):
    dates = await db.get_unique_dates()
    if not dates:
        await callback.answer("У вас нет созданных окон для удаления", show_alert=True)
        return
    await callback.message.edit_text(
        "Выберите дату, чтобы увидеть и удалить слоты:",
        reply_markup=get_admin_delete_dates_kb(dates)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("del_date_"))
async def list_slots_for_delete(callback: CallbackQuery):
    date_str = callback.data.replace("del_date_", "")
    slots = await db.get_slots_by_date(date_str)
    builder = InlineKeyboardBuilder()
    for slot in slots:
        status = "🔴" if slot['is_booked'] else "🟢"
        builder.button(
            text=f"{status} {slot['time']}",
            callback_data=f"confirm_del_{slot['id']}"
        )
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="« Назад к датам", callback_data="admin_delete_slots"))
    builder.row(InlineKeyboardButton(text="🏠 В главное меню", callback_data="admin_main_menu"))
    await callback.message.edit_text(
        f"Слоты на {date_str}:\n🟢 - свободно, 🔴 - забронировано.\nНажмите на слот, чтобы удалить его.",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_del_"))
async def confirm_delete_slot(callback: CallbackQuery):
    slot_id = callback.data.split("_")[2]
    await db.delete_slot(slot_id)
    await callback.message.edit_text("✅ Слот удалён!", reply_markup=get_admin_main_kb())
    await callback.answer()

# --- АВТОРИЗАЦИЯ АДМИНА ---
@router.message(F.text == "/admin")
async def cmd_admin(message: Message, state: FSMContext):
    if message.from_user.id != config.ADMIN_ID:
        return
    saved_pass = await db.get_admin_password()
    if not saved_pass:
        await message.answer("👋 Первый запуск! Придумайте пароль:")
        await state.set_state(AdminStates.waiting_for_new_password)
    else:
        await message.answer("🔐 Введите пароль администратора:")
        await state.set_state(AdminStates.waiting_for_password)

@router.message(AdminStates.waiting_for_new_password)
async def create_pass(message: Message, state: FSMContext):
    await db.set_admin_password(message.text)
    await message.delete()
    await message.answer("✅ Пароль установлен! Введите его для входа:")
    await state.set_state(AdminStates.waiting_for_password)

@router.message(AdminStates.waiting_for_password)
async def check_pass(message: Message, state: FSMContext):
    saved_pass = await db.get_admin_password()
    if message.text == saved_pass:
        await message.delete()
        await state.clear()
        await message.answer("🛠 Панель мастера:", reply_markup=get_admin_main_kb())
    else:
        await message.answer("❌ Неверно! Попробуйте снова:")

# --- ДОБАВЛЕНИЕ СЛОТОВ ---
@router.callback_query(F.data == "admin_add_slot")
async def add_slot_start(callback: CallbackQuery, state: FSMContext):
    now = datetime.now()
    calendar_kb = await kb.generate_calendar(now.month, now.year, [], is_admin=True)
    await callback.message.edit_text("Выберите дату:", reply_markup=calendar_kb)
    await state.set_state(AdminStates.adding_slot_date)

@router.callback_query(AdminStates.adding_slot_date, F.data.startswith("date_"))
async def admin_date_sel(callback: CallbackQuery, state: FSMContext):
    date = callback.data.split("_")[1]
    await state.update_data(date=date)
    await callback.message.edit_text(
        f"📅 Дата: {date}\nВведите время (напр: 10:00 12:00) или выберите шаблон:",
        reply_markup=admin_time_templates()
    )
    await state.set_state(AdminStates.adding_slot_time)
    await callback.answer()

# --- ШАБЛОНЫ ВРЕМЕНИ ---
@router.callback_query(AdminStates.adding_slot_time, F.data.startswith("tpl_"))
async def admin_tpl(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    date = data['date']
    templates = {
        "tpl_morning": ["09:00", "11:00", "13:00"],
        "tpl_afternoon": ["14:00", "16:00", "18:00"],
        "tpl_evening": ["19:00", "21:00"],
        "tpl_fullday": ["09:00", "12:00", "15:00", "18:00"]
    }
    selected_times = templates.get(callback.data)
    if not selected_times:
        await callback.answer("❌ Неизвестный шаблон", show_alert=True)
        return
    for time in selected_times:
        await db.add_slot(date, time)
    await callback.message.edit_text(
        f"✅ Добавлено {len(selected_times)} слотов на {date}",
        reply_markup=get_admin_main_kb()
    )
    await callback.answer()
    await state.clear()

# --- Ввод времени вручную ---
@router.message(AdminStates.adding_slot_time)
async def admin_multi_t(message: Message, state: FSMContext):
    data = await state.get_data()
    date = data['date']
    times = re.findall(r"\d{1,2}:\d{2}", message.text)
    if not times:
        await message.answer("❌ Не найдено время в формате ЧЧ:ММ. Попробуйте снова:")
        return
    for t in times:
        await db.add_slot(date, t)
    await message.answer(
        f"✅ Добавлено: {', '.join(times)}",
        reply_markup=get_admin_main_kb()
    )
    await state.clear()

# --- УСЛУГИ ---
@router.callback_query(F.data == "admin_setup_services")
async def setup_services(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📜 Шаг 1: Основные услуги (название - цена):")
    await state.set_state(AdminStates.filling_main_services)
    await callback.answer()

@router.message(AdminStates.filling_main_services)
async def step2(message: Message, state: FSMContext):
    await db.update_service_block('main_services', message.text)
    await message.answer("➕ Шаг 2: Доп. услуги:")
    await state.set_state(AdminStates.filling_add_services)

@router.message(AdminStates.filling_add_services)
async def step3(message: Message, state: FSMContext):
    await db.update_service_block('add_services', message.text)
    await message.answer("🛡 Шаг 3: Гарантия:")
    await state.set_state(AdminStates.filling_warranty)

@router.message(AdminStates.filling_warranty)
async def step_fin(message: Message, state: FSMContext):
    await db.update_service_block('warranty', message.text)
    await message.answer("✅ Услуги обновлены!", reply_markup=get_admin_main_kb())
    await state.clear()

# --- РАССЫЛКА ---
@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📢 Введите текст рассылки:")
    await state.set_state(AdminStates.broadcast_message)
    await callback.answer()

@router.message(AdminStates.broadcast_message)
async def broadcast_send(message: Message, state: FSMContext):
    users = await db.get_all_users()
    sent = 0
    for user_id in users:
        try:
            await message.copy_to(user_id)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"Не удалось отправить пользователю {user_id}: {e}")
    await message.answer(f"✅ Рассылка завершена! Отправлено: {sent} пользователям", reply_markup=get_admin_main_kb())
    await state.clear()

# --- ПРОСМОТР ЗАПИСЕЙ ---
@router.callback_query(F.data == "admin_view_schedule")
async def view_sch(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📅 Введите дату (например, 12.01):")
    await state.set_state(AdminStates.view_schedule_date)
    await callback.answer()

@router.message(AdminStates.view_schedule_date)
async def view_res(message: Message, state: FSMContext):
    date = message.text.strip()
    res = await db.get_admin_schedule(date)
    if not res:
        await message.answer("❌ На эту дату нет записей.")
    else:
        txt = f"📅 {date}:\n\n"
        for b in res:
            txt += f"⏰ {b['time']} — {b['user_name']} ({b['user_phone']})\n"
        await message.answer(txt)
    await message.answer("Выберите действие:", reply_markup=get_admin_main_kb())
    await state.clear()

# --- ПОРТФОЛИО ---
@router.callback_query(F.data == "admin_set_portfolio")
async def set_port(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🖼 Введите новую ссылку на портфолио:")
    await state.set_state(AdminStates.setting_portfolio)
    await callback.answer()

@router.message(AdminStates.setting_portfolio)
async def port_res(message: Message, state: FSMContext):
    await db.set_portfolio(message.text)
    await message.answer("✅ Ссылка на портфолио обновлена!", reply_markup=get_admin_main_kb())
    await state.clear()
