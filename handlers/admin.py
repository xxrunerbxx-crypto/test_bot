import os
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
import keyboards as kb
from states import AdminStates

router = Router()

# --- ВХОД В АДМИНКУ (БЕЗ ПАРОЛЯ) ---
@router.message(Command("admin"))
async def admin_start(message: Message, state: FSMContext):
    await state.clear() # Сбрасываем всё при входе
    await message.answer(
        "👋 Добро пожаловать в панель администратора!", 
        reply_markup=kb.get_admin_main_kb()
    )

# --- ГЛОБАЛЬНАЯ НАВИГАЦИЯ (ВЫХОД В МЕНЮ) ---
@router.callback_query(F.data == "admin_main_menu")
async def back_to_admin_main(callback: CallbackQuery, state: FSMContext):
    await state.clear() # Сбрасываем любые состояния
    await callback.message.edit_text(
        "👋 Главное меню администратора:",
        reply_markup=kb.get_admin_main_kb()
    )
    await callback.answer()

# --- ДОБАВЛЕНИЕ ОКОН ---
@router.callback_query(F.data == "admin_add_slots")
async def add_slots_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(AdminStates.adding_slots)
    # Используем твой генератор календаря, но с кнопкой отмены
    await callback.message.edit_text(
        "Выберите дату в календаре или введите (ДД.ММ.ГГГГ):",
        reply_markup=kb.get_admin_cancel_kb() 
    )
    await callback.answer()

# --- УДАЛЕНИЕ ОКОН (ИСПРАВЛЕННОЕ) ---
@router.callback_query(F.data == "admin_delete_slots")
async def process_delete_slots(callback: CallbackQuery, state: FSMContext):
    await state.clear() # Чтобы не "висело" ожидание ввода даты
    dates = await db.get_unique_dates()
    
    if not dates:
        await callback.answer("У вас нет созданных окон!", show_alert=True)
        return

    await callback.message.edit_text(
        "Выберите дату для удаления окон:",
        reply_markup=kb.get_admin_delete_dates_kb(dates)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("del_date_"))
async def list_slots_for_delete(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.replace("del_date_", "")
    slots = await db.get_slots_by_date(date_str)
    
    builder = InlineKeyboardBuilder()
    for slot in slots:
        # slot[0]=id, slot[1]=time, slot[2]=is_booked
        status = "🔴" if slot[2] else "🟢"
        builder.button(
            text=f"{status} {slot[1]}", 
            callback_data=f"confirm_del_{slot[0]}"
        )
    
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="« Назад к датам", callback_data="admin_delete_slots"))
    builder.row(InlineKeyboardButton(text="🏠 В главное меню", callback_data="admin_main_menu"))
    
    await callback.message.edit_text(
        f"Удаление на {date_str}:\nНажмите на слот для удаления.",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_del_"))
async def delete_slot_action(callback: CallbackQuery):
    slot_id = int(callback.data.replace("confirm_del_", ""))
    await db.delete_slot(slot_id)
    await callback.answer("Слот удален")
    
    # Сразу обновляем список дат
    dates = await db.get_unique_dates()
    if dates:
        await callback.message.edit_text(
            "Слот удален. Выберите дату для продолжения:",
            reply_markup=kb.get_admin_delete_dates_kb(dates)
        )
    else:
        await callback.message.edit_text(
            "Все слоты удалены.",
            reply_markup=kb.get_admin_main_kb()
        )

# --- РАССЫЛКА ---
@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(AdminStates.broadcasting)
    await callback.message.edit_text(
        "Введите текст сообщения для рассылки всем пользователям:",
        reply_markup=kb.get_admin_cancel_kb()
    )
    await callback.answer()

@router.message(AdminStates.broadcasting)
async def do_broadcast(message: Message, state: FSMContext):
    users = await db.get_all_users()
    count = 0
    for user_id in users:
        try:
            await message.copy_to(user_id)
            count += 1
        except:
            pass
    await state.clear()
    await message.answer(
        f"✅ Рассылка завершена! Получили: {count}", 
        reply_markup=kb.get_admin_main_kb()
    )

# --- УСЛУГИ ---
@router.callback_query(F.data == "admin_services_conf")
async def services_conf(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "⚙️ Управление услугами:",
        reply_markup=kb.get_admin_cancel_kb()
    )
    await callback.answer()