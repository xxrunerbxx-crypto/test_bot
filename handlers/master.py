from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import db
from keyboards.calendar_kb import generate_calendar
from services.subscription_service import subscription_service
from utils.states import MasterStates

router = Router()


def master_menu(days_left: str):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📅 Слоты", callback_data="m_calendar"))
    kb.row(InlineKeyboardButton(text="📊 Статистика", callback_data="m_stats"))
    kb.row(InlineKeyboardButton(text="⚙️ Услуги", callback_data="m_services"))
    kb.row(InlineKeyboardButton(text="📸 Портфолио", callback_data="m_portfolio"))
    kb.row(InlineKeyboardButton(text=f"💎 Подписка ({days_left} дн.)", callback_data="m_subscription_info"))
    return kb.as_markup()


async def _render_day(message, master_id: int, date: str):
    slots = db.get_admin_slots(master_id, date)
    text = f"Дата: {date}\n\n"
    for slot in slots:
        text += f"{'🔴' if slot['booked'] else '🟢'} {slot['time']}\n"
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="⚡ Авто 10:00-19:00", callback_data=f"m_auto_{date}"))
    kb.row(InlineKeyboardButton(text="🗑 Очистить свободные", callback_data=f"m_clear_{date}"))
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="m_calendar"))
    await message.edit_text(text, reply_markup=kb.as_markup())


@router.message(Command("admin"))
async def master_admin(message: Message):
    subscription_service.ensure_master(message.from_user.id)
    access, days_left = subscription_service.check_access(message.from_user.id)
    if not access:
        return await message.answer("Подписка истекла. Обратитесь к владельцу бота.")
    me = await message.bot.get_me()
    link = f"https://t.me/{me.username}?start={message.from_user.id}"
    await message.answer(
        f"Панель мастера\nСсылка для клиентов:\n<code>{link}</code>",
        parse_mode="HTML",
        reply_markup=master_menu(days_left),
    )


@router.callback_query(F.data == "m_stats")
async def m_stats(callback: CallbackQuery):
    stats = db.get_master_stats(callback.from_user.id)
    await callback.message.edit_text(
        f"📊 Статистика\n\nВсего: {stats['total']}\nАктивные: {stats['active']}\nРейтинг: {stats['rating']}",
    )


@router.callback_query(F.data == "m_calendar")
async def m_calendar(callback: CallbackQuery):
    now = datetime.now()
    await callback.message.edit_text(
        "Выберите дату:",
        reply_markup=generate_calendar(now.year, now.month, callback.from_user.id, is_admin=True),
    )


@router.callback_query(F.data.startswith("admin_date_"))
async def m_day(callback: CallbackQuery):
    date = callback.data.split("_")[2]
    await _render_day(callback.message, callback.from_user.id, date)


@router.callback_query(F.data.startswith("m_auto_"))
async def m_auto(callback: CallbackQuery):
    date = callback.data.split("_")[2]
    for t in ["10:00", "11:30", "13:00", "14:30", "16:00", "17:30", "19:00"]:
        db.add_slot(callback.from_user.id, f"{date} {t}")
    await _render_day(callback.message, callback.from_user.id, date)


@router.callback_query(F.data.startswith("m_clear_"))
async def m_clear(callback: CallbackQuery):
    date = callback.data.split("_")[2]
    db.clear_free_slots_for_date(callback.from_user.id, date)
    await _render_day(callback.message, callback.from_user.id, date)


@router.callback_query(F.data == "m_services")
async def m_services_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MasterStates.waiting_main)
    await callback.message.edit_text("Шаг 1/4: Основные услуги")


@router.message(MasterStates.waiting_main)
async def m_services_2(message: Message, state: FSMContext):
    db.update_master_profile(message.from_user.id, "main_services", message.text or "")
    await state.set_state(MasterStates.waiting_additional)
    await message.answer("Шаг 2/4: Доп. услуги")


@router.message(MasterStates.waiting_additional)
async def m_services_3(message: Message, state: FSMContext):
    db.update_master_profile(message.from_user.id, "additional_services", message.text or "")
    await state.set_state(MasterStates.waiting_warranty)
    await message.answer("Шаг 3/4: Гарантия")


@router.message(MasterStates.waiting_warranty)
async def m_services_4(message: Message, state: FSMContext):
    db.update_master_profile(message.from_user.id, "warranty", message.text or "")
    await state.set_state(MasterStates.waiting_photo)
    await message.answer("Шаг 4/4: Отправьте фото или /skip")


@router.message(MasterStates.waiting_photo, F.photo)
async def m_services_photo(message: Message, state: FSMContext):
    db.update_master_profile(message.from_user.id, "photo_id", message.photo[-1].file_id)
    await state.clear()
    await message.answer("Профиль услуг обновлен.")


@router.message(Command("skip"), MasterStates.waiting_photo)
async def m_skip_photo(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Профиль услуг обновлен без фото.")


@router.callback_query(F.data == "m_portfolio")
async def m_portfolio_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MasterStates.waiting_portfolio)
    await callback.message.edit_text("Пришлите ссылку на портфолио:")


@router.message(MasterStates.waiting_portfolio)
async def m_portfolio_save(message: Message, state: FSMContext):
    text = message.text or ""
    if not text.startswith("http"):
        return await message.answer("Ссылка должна начинаться с http.")
    db.update_master_profile(message.from_user.id, "portfolio_link", text)
    await state.clear()
    await message.answer("Ссылка сохранена.")
