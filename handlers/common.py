from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database import db
import keyboards as kb

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await db.add_user(message.from_user.id) # СОХРАНЯЕМ ПОЛЬЗОВАТЕЛЯ В БАЗУ
    await message.answer(f"Привет, {message.from_user.first_name}! ✨", reply_markup=kb.main_menu())

@router.callback_query(F.data == "to_main")
async def to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Главное меню:", reply_markup=kb.main_menu())