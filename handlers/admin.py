from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

import database as db
import keyboards as kb
from states import AdminStates

router = Router()

# Универсальный выход
@router.callback_query(F.data == "admin_main_menu")
async def back_to_admin_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "👋 Главное меню администратора:",
        reply_markup=kb.get_admin_main_kb()
    )
    await callback.answer()

@router.message(Command("admin"))
async def admin_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🛠 **Панель управления мастером**",
        reply_markup=kb.get_admin_main_kb()
    )

# --- ДОБАВЛЕНИЕ ОКОН ---
@router.callback_query(F.data == "admin_add_slot")
async def add_slots_step1(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(AdminStates.adding_slot_date)
    # Показываем твой календарь
    now = datetime.now()
    await callback.message.edit_text(
        "📅 Выберите дату для добавления окон:",
        reply_markup=await kb.generate_calendar(now.month, now.year, [], is_admin=True)
    )

@router.callback_query(AdminStates.adding_slot_date, F.data.startswith("admin_date_"))
async def add_slots_step2(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.replace("admin_date_", "")
    await state.update_data(chosen_date=date_str)
    await state.set_state(AdminStates.adding_slot_time)
    
    # Показываем твои шаблоны времени
    await callback.message.edit_text(
        f"📅 Дата: {date_str}\n\nВыберите шаблон или введите время вручную (напр. 10:00, 12:00):",
        reply_markup=kb.admin_time_templates()
    )

# Обработка ручного ввода времени
@router.message(AdminStates.adding_slot_time)
async def process_manual_time(message: Message, state: FSMContext):
    data = await state.get_data()
    date = data['chosen_date']
    times = [t.strip() for t in message.text.split(',')]
    
    for t in times:
        await db.add_slot(date, t) # Предполагаем, что функция в db есть
        
    await state.clear()
    await message.answer(f"✅ Окна на {date} успешно добавлены: {', '.join(times)}", 
                         reply_markup=kb.get_admin_main_kb())

# --- УДАЛЕНИЕ ОКОН ---
@router.callback_query(F.data == "admin_delete_slots")
async def process_delete_slots(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    dates = await db.get_unique_dates()
    if not dates:
        await callback.answer("❌ Нет окон для удаления", show_alert=True)
        return
    await callback.message.edit_text("🗑 Выберите дату для удаления:", 
                                     reply_markup=kb.get_admin_delete_dates_kb(dates))

@router.callback_query(F.data.startswith("del_date_"))
async def list_slots_to_del(callback: CallbackQuery):
    date_str = callback.data.replace("del_date_", "")
    slots = await db.get_slots_by_date(date_str)
    builder = InlineKeyboardBuilder()
    for s in slots:
        status = "🔴" if s[2] else "🟢"
        builder.button(text=f"{status} {s[1]}", callback_data=f"confirm_del_{s[0]}")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="« Назад", callback_data="admin_delete_slots"))
    await callback.message.edit_text(f"Удаление на {date_str}:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("confirm_del_"))
async def del_slot_final(callback: CallbackQuery):
    await db.delete_slot(int(callback.data.replace("confirm_del_", "")))
    await callback.answer("Удалено")
    # Возврат к датам
    dates = await db.get_unique_dates()
    if dates:
        await callback.message.edit_text("Выберите дату:", reply_markup=kb.get_admin_delete_dates_kb(dates))
    else:
        await callback.message.edit_text("Все окна удалены.", reply_markup=kb.get_admin_main_kb())

# --- РАССЫЛКА ---
@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.broadcasting)
    await callback.message.edit_text("📢 Введите текст рассылки:", reply_markup=kb.get_admin_cancel_kb())

@router.message(AdminStates.broadcasting)
async def cmd_broadcast(message: Message, state: FSMContext):
    users = await db.get_all_users()
    for u in users:
        try: await message.copy_to(u)
        except: pass
    await state.clear()
    await message.answer("✅ Рассылка завершена", reply_markup=kb.get_admin_main_kb())

# --- УСЛУГИ (ИСПРАВЛЕНО: callback теперь совпадает с кнопкой) ---
@router.callback_query(F.data == "admin_setup_services")
async def admin_services(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "⚙️ **Настройка услуг**\nВыберите блок для редактирования:",
        reply_markup=kb.get_admin_cancel_kb()
    )

# --- ПОРТФОЛИО (ИСПРАВЛЕНО: callback теперь совпадает с кнопкой) ---
@router.callback_query(F.data == "admin_set_portfolio")
async def admin_portfolio(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🖼 **Настройка портфолио**\nОтправьте новую ссылку или фото:",
        reply_markup=kb.get_admin_cancel_kb()
    )