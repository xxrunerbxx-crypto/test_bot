import re
import asyncio
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest # Импортируем для отлова ошибки
from aiogram.utils.keyboard import InlineKeyboardBuilder  
from aiogram.types import InlineKeyboardButton         

import config
from database import db
import keyboards as kb
from states import AdminStates

router = Router()

# ========================================================================
# ВХОД В АДМИНКУ
# ========================================================================
@router.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    """Логика входа: проверяем наличие пароля в базе"""
    # 1. Защита по ID (только владелец)
    if message.from_user.id != config.ADMIN_ID:
        return

    # 2. Проверяем, установлен ли пароль в базе данных
    saved_password = await db.get_admin_password()

    if not saved_password:
        # Если пароля нет (самый первый запуск)
        await message.answer("👋 <b>Первый запуск!</b>\nПожалуйста, придумайте и введите пароль для админ-панели:")
        await state.set_state(AdminStates.waiting_for_new_password)
    else:
        # Если пароль уже есть в базе
        await message.answer("🔐 <b>Доступ ограничен.</b>\nВведите пароль администратора:")
        await state.set_state(AdminStates.waiting_for_password)

@router.message(AdminStates.waiting_for_new_password)
async def create_admin_password(message: types.Message, state: FSMContext):
    """Сохраняем новый пароль в базу"""
    new_pass = message.text
    await db.set_admin_password(new_pass) # Сохраняем в таблицу settings
    await message.delete() # Удаляем пароль из чата для безопасности
    await message.answer("✅ <b>Пароль успешно установлен!</b>\nТеперь введите его для подтверждения входа:")
    await state.set_state(AdminStates.waiting_for_password)

@router.message(AdminStates.waiting_for_password)
async def check_admin_password(message: types.Message, state: FSMContext):
    """Сверяем введенный пароль с тем, что в базе"""
    saved_password = await db.get_admin_password()
    
    if message.text == saved_password:
        await message.delete() # Удаляем пароль из чата
        await state.clear()
        await message.answer("🛠 <b>Панель мастера:</b>", reply_markup=kb.admin_menu())
    else:
        await message.answer("❌ <b>Неверный пароль!</b>\nПопробуйте еще раз:")
# ========================================================================
# НАСТРОЙКА УСЛУГ (Основные -> Доп -> Гарантия)
# ========================================================================
# Проверь, что в keyboards.py у этой кнопки callback_data="admin_setup_services"
@router.callback_query(F.data == "admin_setup_services")
async def admin_services_step1(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📜 <b>Шаг 1/3: Основные услуги</b>\nВведите список услуг и цен (одним сообщением):")
    await state.set_state(AdminStates.filling_main_services)

@router.message(AdminStates.filling_main_services)
async def admin_services_step2(message: types.Message, state: FSMContext):
    await db.update_service_block('main_services', message.text)
    await message.answer("➕ <b>Шаг 2/3: Дополнительные услуги</b>\nВведите список доп. услуг:")
    await state.set_state(AdminStates.filling_add_services)

@router.message(AdminStates.filling_add_services)
async def admin_services_step3(message: types.Message, state: FSMContext):
    await db.update_service_block('add_services', message.text)
    await message.answer("🛡 <b>Шаг 3/3: Гарантия</b>\nНапишите условия вашей гарантии:")
    await state.set_state(AdminStates.filling_warranty)

@router.message(AdminStates.filling_warranty)
async def admin_services_final(message: types.Message, state: FSMContext):
    await db.update_service_block('warranty', message.text)
    await message.answer("✅ <b>Все разделы услуг успешно обновлены!</b>", reply_markup=kb.admin_menu())
    await state.clear()

# ========================================================================
# ДОБАВЛЕНИЕ СЛОТОВ (С ЗАЩИТОЙ ОТ ОШИБКИ ТЕЛЕГРАМА)
# ========================================================================
@router.callback_query(F.data == "admin_add_slot")
async def admin_add_slot_start(callback: types.CallbackQuery, state: FSMContext):
    now = datetime.now()
    calendar_markup = await kb.generate_calendar(now.month, now.year, [], is_admin=True)
    try:
        await callback.message.edit_text("📅 <b>Выберите дату для добавления окон:</b>", reply_markup=calendar_markup)
    except TelegramBadRequest: # Если меню уже такое же - просто игнорируем ошибку
        pass
    await state.set_state(AdminStates.adding_slot_date)

@router.callback_query(AdminStates.adding_slot_date)
async def admin_date_selected(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "ignore": 
        await callback.answer()
        return
    
    date = callback.data.split("_")[1]
    await state.update_data(date=date)
    
    try:
        await callback.message.edit_text(
            f"📅 <b>Дата: {date}</b>\n\nВведите время через пробел или выберите шаблон:",
            reply_markup=kb.admin_time_templates()
        )
    except TelegramBadRequest:
        pass
    await state.set_state(AdminStates.adding_slot_time)

# --- Далее идут хэндлеры шаблонов и мульти-ввода времени ---
@router.callback_query(AdminStates.adding_slot_time, F.data.startswith("tpl_"))
async def admin_template_time(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    date = data['date']
    templates = {
        "tpl_morning": ["09:00", "11:00", "13:00"],
        "tpl_afternoon": ["14:00", "16:00", "18:00"],
        "tpl_evening": ["19:00", "21:00"],
        "tpl_fullday": ["09:00", "12:00", "15:00", "18:00", "21:00"]
    }
    selected_times = templates.get(callback.data)
    for t in selected_times:
        await db.add_slot(date, t)
    await callback.message.answer(f"✅ На {date} добавлено {len(selected_times)} окон!", reply_markup=kb.admin_menu())
    await state.clear()

@router.message(AdminStates.adding_slot_time)
async def admin_multi_time(message: types.Message, state: FSMContext):
    data = await state.get_data()
    date = data['date']
    times = re.findall(r"\d{1,2}:\d{2}", message.text)
    if not times:
        await message.answer("❌ Введите время корректно (напр. 10:00 12:00)")
        return
    for t in times:
        await db.add_slot(date, t)
    await message.answer(f"✅ На {date} добавлено окон: {', '.join(times)}", reply_markup=kb.admin_menu())
    await state.clear()

# ========================================================================
# ПРОСМОТР РАСПИСАНИЯ
# ========================================================================
@router.callback_query(F.data == "admin_view_schedule")
async def admin_view_schedule(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите дату (напр. 15.01):")
    await state.set_state(AdminStates.view_schedule_date)

@router.message(AdminStates.view_schedule_date)
async def process_view_schedule(message: types.Message, state: FSMContext):
    if message.from_user.id != config.ADMIN_ID: return
    bookings = await db.get_admin_schedule(message.text)
    if not bookings:
        await message.answer(f"На {message.text} записей нет.")
    else:
        res = f"📅 <b>Записи на {message.text}:</b>\n\n"
        for b in bookings:
            res += f"⏰ {b['time']} — {b['user_name']} (<code>{b['user_phone']}</code>)\n"
        await message.answer(res, reply_markup=kb.admin_menu())
    await state.clear()

@router.callback_query(F.data == "admin_set_portfolio")
async def admin_portfolio(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите ссылку на портфолио:")
    await state.set_state(AdminStates.setting_portfolio)

@router.message(AdminStates.setting_portfolio)
async def admin_portfolio_res(message: types.Message, state: FSMContext):
    await db.set_portfolio(message.text)
    await message.answer("✅ Ссылка сохранена!", reply_markup=kb.admin_menu())
    await state.clear()

# --- РАССЫЛКА ---
@router.callback_query(F.data == "admin_broadcast")
async def broadcast_step1(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📢 <b>Введите текст рассылки.</b>\nЕго получат ВСЕ пользователи бота.")
    await state.set_state(AdminStates.broadcast_message) # Добавь в states.py

@router.message(AdminStates.broadcast_message)
async def broadcast_step2(message: types.Message, state: FSMContext):
    users = await db.get_all_users()
    count = 0
    for u_id in users:
        try:
            await message.copy_to(u_id) # Копирует сообщение (текст, фото, видео)
            count += 1
            await asyncio.sleep(0.05) # Защита от спам-фильтра телеграма
        except:
            pass
    await message.answer(f"✅ Рассылка завершена! Получили: {count} чел.", reply_markup=kb.admin_menu())
    await state.clear()

# --- УДАЛЕНИЕ СЛОТОВ ---
@router.callback_query(F.data == "admin_delete_slots")
async def delete_slots_step1(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите дату, чтобы увидеть свободные окна для удаления (напр. 15.01):")
    await state.set_state(AdminStates.deleting_slot_date)

@router.message(AdminStates.deleting_slot_date)
async def delete_slots_step2(message: types.Message, state: FSMContext):
    slots = await db.get_slots_by_date(message.text)
    if not slots:
        await message.answer("На эту дату нет свободных окон.")
        return
    
    # Создаем кнопки для каждого слота, чтобы мастер мог нажать и удалить
    builder = InlineKeyboardBuilder()
    for s_id, s_time in slots:
        builder.row(InlineKeyboardButton(text=f"Удалить {s_time}", callback_data=f"del_slot_{s_id}"))
    builder.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_menu"))
    
    await message.answer(f"Выберите окно на {message.text} для удаления:", reply_markup=builder.as_markup())
    await state.clear()

@router.callback_query(F.data.startswith("del_slot_"))
async def process_delete_slot(callback: types.CallbackQuery):
    s_id = callback.data.split("_")[2]
    await db.delete_slot(s_id)
    await callback.message.edit_text("✅ Окно успешно удалено!", reply_markup=kb.admin_menu())