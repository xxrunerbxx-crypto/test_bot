from aiogram import F, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_ID
from database.db import db
from services.subscription_service import subscription_service
from utils.states import OwnerAdminStates

router = Router()


def owner_menu():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="👥 Пользователи", callback_data="o_users_0"))
    kb.row(InlineKeyboardButton(text="👤 Мастера/подписки", callback_data="o_masters"))
    kb.row(InlineKeyboardButton(text="🗂 Записи", callback_data="o_bookings_0"))
    kb.row(InlineKeyboardButton(text="📣 Рассылка", callback_data="o_broadcast"))
    kb.row(InlineKeyboardButton(text="🛠 Техработы", callback_data="o_maintenance"))
    return kb.as_markup()


async def render_owner_panel(event):
    users_count = db.count_users()
    masters_count = len(db.list_masters())
    bookings_count = db.count_bookings()
    maintenance = db.get_maintenance()
    text = (
        "Панель владельца\n\n"
        f"Пользователи: {users_count}\n"
        f"Мастера: {masters_count}\n"
        f"Записи: {bookings_count}\n"
        f"Техработы: {'ВКЛ' if maintenance['enabled'] else 'ВЫКЛ'}"
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=owner_menu())
    else:
        await event.answer(text, reply_markup=owner_menu())


@router.message(Command("activate"))
async def activate_manual(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        args = message.text.split()
        target_id = int(args[1])
        days = int(args[2])
        new_date = subscription_service.activate(target_id, days)
        await message.answer(f"Подписка мастера {target_id} активна до {new_date}")
    except Exception:
        await message.answer("Формат: /activate [master_id] [days]")


@router.message(Command("owner"))
async def owner_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    db.upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name, "owner")
    await render_owner_panel(message)


@router.callback_query(F.data.startswith("o_users_"))
async def owner_users(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    offset = int(callback.data.split("_")[-1])
    rows = db.list_users(limit=20, offset=offset)
    total = db.count_users()
    text = "Пользователи:\n\n" + "\n".join([f"{r['id']} | {r['first_name'] or r['username'] or '-'}" for r in rows]) if rows else "Пусто"
    kb = InlineKeyboardBuilder()
    if offset > 0:
        kb.row(InlineKeyboardButton(text="⬅️", callback_data=f"o_users_{max(0, offset - 20)}"))
    if offset + 20 < total:
        kb.row(InlineKeyboardButton(text="➡️", callback_data=f"o_users_{offset + 20}"))
    kb.row(InlineKeyboardButton(text="⬅️ В панель", callback_data="o_back"))
    await callback.message.edit_text(text, reply_markup=kb.as_markup())


@router.callback_query(F.data == "o_masters")
async def owner_masters(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    masters = db.list_masters()
    text = "Мастера:\n\n" + "\n".join([f"{m['user_id']} -> {m['subscription_until']}" for m in masters[:50]]) if masters else "Пусто"
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="➕ Продлить (id days)", callback_data="o_extend"))
    kb.row(InlineKeyboardButton(text="⬅️ В панель", callback_data="o_back"))
    await callback.message.edit_text(text, reply_markup=kb.as_markup())


@router.callback_query(F.data == "o_extend")
async def owner_extend_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.clear()
    await state.set_state(OwnerAdminStates.waiting_subscription_input)
    await callback.message.edit_text("Введите: master_id days")


@router.message(OwnerAdminStates.waiting_subscription_input)
async def owner_extend_apply(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        return await message.answer("Формат: master_id days")
    new_date = subscription_service.activate(int(parts[0]), int(parts[1]))
    await message.answer(f"Подписка продлена до {new_date}")
    await state.clear()

@router.callback_query(F.data.startswith("o_bookings_"))
async def owner_bookings(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    offset = int(callback.data.split("_")[-1])
    rows = db.list_bookings(limit=20, offset=offset)
    total = db.count_bookings()
    text = "Записи:\n\n" + "\n".join([f"{r['id']} | m:{r['master_id']} u:{r['user_id']} {r['status']}" for r in rows]) if rows else "Пусто"
    kb = InlineKeyboardBuilder()
    if offset > 0:
        kb.row(InlineKeyboardButton(text="⬅️", callback_data=f"o_bookings_{max(0, offset - 20)}"))
    if offset + 20 < total:
        kb.row(InlineKeyboardButton(text="➡️", callback_data=f"o_bookings_{offset + 20}"))
    kb.row(InlineKeyboardButton(text="⬅️ В панель", callback_data="o_back"))
    await callback.message.edit_text(text, reply_markup=kb.as_markup())


@router.callback_query(F.data == "o_maintenance")
async def owner_maintenance(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    m = db.get_maintenance()
    db.set_maintenance(not m["enabled"])
    await render_owner_panel(callback)


@router.callback_query(F.data == "o_broadcast")
async def owner_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(OwnerAdminStates.waiting_broadcast_text)
    await callback.message.edit_text("Введите текст рассылки.")


@router.message(OwnerAdminStates.waiting_broadcast_text)
async def owner_broadcast_preview(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.update_data(broadcast_text=message.text or "")
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Отправить", callback_data="o_broadcast_send"))
    kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="o_back"))
    await state.set_state(OwnerAdminStates.waiting_broadcast_confirm)
    await message.answer("Подтвердите рассылку.", reply_markup=kb.as_markup())


@router.callback_query(F.data == "o_broadcast_send")
async def owner_broadcast_send(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    text = data.get("broadcast_text", "").strip()
    sent = 0
    failed = 0
    for uid in db.get_all_user_ids():
        try:
            await callback.bot.send_message(uid, text)
            sent += 1
        except TelegramForbiddenError:
            failed += 1
        except Exception:
            failed += 1
    await state.clear()
    await callback.message.edit_text(f"Рассылка завершена. Успешно: {sent}, ошибок: {failed}", reply_markup=owner_menu())


@router.callback_query(F.data == "o_back")
async def owner_back(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.clear()
    await render_owner_panel(callback)