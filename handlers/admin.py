from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
import keyboards as kb
from states import AdminStates

router = Router()

# Универсальный обработчик возврата, который ничего не удаляет, 
# а просто выводит из любого состояния (FSM)
@router.callback_query(F.data == "admin_main_menu")
async def back_to_admin_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()  # Сбрасываем ожидание ввода, но НЕ данные в БД
    from keyboards import get_admin_main_kb
    await callback.message.edit_text(
        "👋 Главное меню администратора:",
        reply_markup=get_admin_main_kb()
    )
    await callback.answer()

# ==========================================
# 1. ВХОД В АДМИНКУ И ГЛАВНОЕ МЕНЮ
# ==========================================

@router.message(Command("admin"))
async def admin_start(message: Message, state: FSMContext):
    """Вход в админку по команде /admin"""
    await state.clear() # Сброс любых зависших состояний
    await message.answer(
        "🛠 **Панель управления мастером**\nВыберите нужное действие в меню ниже:",
        reply_markup=kb.get_admin_main_kb()
    )

# ==========================================
# 2. ДОБАВЛЕНИЕ СЛОТОВ (ОКОН)
# ==========================================

@router.callback_query(F.data == "admin_add_slots")
async def add_slots_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(AdminStates.adding_slots)
    await callback.message.edit_text(
        "📅 **Добавление новых окон**\n\nВведите дату и время в формате:\n`ДД.ММ.ГГГГ ЧЧ:ММ, ЧЧ:ММ`"
        "\n\nИли выберите дату в календаре (если он подключен).",
        reply_markup=kb.get_admin_cancel_kb() # Кнопка отмены
    )
    await callback.answer()

# Здесь должен быть ваш @router.message(AdminStates.adding_slots) для обработки текста
# Если он у вас в другом файле, убедитесь, что он ловит состояние AdminStates.adding_slots


# ==========================================
# 3. УДАЛЕНИЕ СЛОТОВ (ОКОН)
# ==========================================

@router.callback_query(F.data == "admin_delete_slots")
async def process_delete_slots(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    dates = await db.get_unique_dates()
    
    if not dates:
        await callback.answer("❌ У вас пока нет созданных окон.", show_alert=True)
        return

    await callback.message.edit_text(
        "🗑 **Удаление окон**\nВыберите дату, на которую хотите удалить время:",
        reply_markup=kb.get_admin_delete_dates_kb(dates)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("del_date_"))
async def list_slots_for_delete(callback: CallbackQuery):
    date_str = callback.data.replace("del_date_", "")
    slots = await db.get_slots_by_date(date_str)
    
    builder = InlineKeyboardBuilder()
    for s in slots:
        # s[0]-id, s[1]-time, s[2]-is_booked
        status = "🔴" if s[2] else "🟢"
        builder.button(
            text=f"{status} {s[1]}", 
            callback_data=f"confirm_del_{s[0]}"
        )
    
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="« Назад к датам", callback_data="admin_delete_slots"))
    builder.row(InlineKeyboardButton(text="🏠 В главное меню", callback_data="admin_main_menu"))
    
    await callback.message.edit_text(
        f"📅 Слоты на {date_str}\n🟢 - свободно, 🔴 - занято.\n\nНажмите на время, чтобы **удалить** его:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_del_"))
async def delete_slot_action(callback: CallbackQuery):
    slot_id = int(callback.data.replace("confirm_del_", ""))
    await db.delete_slot(slot_id)
    await callback.answer("✅ Слот удален!")
    
    # Проверяем, остались ли еще даты
    dates = await db.get_unique_dates()
    if dates:
        await callback.message.edit_text(
            "✅ Слот удален. Выберите дату для дальнейшего удаления:",
            reply_markup=kb.get_admin_delete_dates_kb(dates)
        )
    else:
        await callback.message.edit_text(
            "✅ Все слоты были удалены.",
            reply_markup=kb.get_admin_main_kb()
        )


# ==========================================
# 4. РАССЫЛКА ПОЛЬЗОВАТЕЛЯМ
# ==========================================

@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(AdminStates.broadcasting)
    await callback.message.edit_text(
        "📢 **Рассылка сообщений**\n\nВведите текст, который хотите отправить всем вашим клиентам:",
        reply_markup=kb.get_admin_cancel_kb()
    )
    await callback.answer()

@router.message(AdminStates.broadcasting)
async def do_broadcast(message: Message, state: FSMContext):
    users = await db.get_all_users()
    success_count = 0
    
    for u_id in users:
        try:
            await message.copy_to(u_id)
            success_count += 1
        except:
            pass # Если заблокировали бота
            
    await state.clear()
    await message.answer(
        f"✅ Рассылка завершена!\nСообщение получили {success_count} чел.",
        reply_markup=kb.get_admin_main_kb()
    )


# ==========================================
# 5. НАСТРОЙКА УСЛУГ И ПОРТФОЛИО
# ==========================================

@router.callback_query(F.data == "admin_services_conf")
async def services_conf(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    # Здесь в будущем можно добавить логику редактирования
    await callback.message.edit_text(
        "⚙️ **Настройка услуг**\n\nВ этом разделе можно изменить список услуг, цены и описание блоков (Основные, Доп, Гарантия).",
        reply_markup=kb.get_admin_cancel_kb()
    )
    await callback.answer()

@router.callback_query(F.data == "admin_portfolio")
async def portfolio_conf(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    # Здесь можно добавить логику изменения ссылки на портфолио
    await callback.message.edit_text(
        "📂 **Ваше портфолио**\n\nЗдесь можно настроить ссылку на ваши работы или загрузить фотографии в бота.",
        reply_markup=kb.get_admin_cancel_kb()
    )
    await callback.answer()