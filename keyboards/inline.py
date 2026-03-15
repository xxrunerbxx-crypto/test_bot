from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

def main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💅 Записаться", callback_data="start_booking"))
    builder.row(InlineKeyboardButton(text="❌ Отменить запись", callback_data="cancel_booking"))
    builder.row(InlineKeyboardButton(text="💰 Прайсы", callback_data="prices"),
                InlineKeyboardButton(text="📸 Портфолио", callback_data="portfolio"))
    return builder.as_markup()

def sub_check_kb(link):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Подписаться", url=link))
    builder.row(InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub"))
    return builder.as_markup()

def back_kb():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="to_main"))
    return builder.as_markup()

def nav_btns():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_step"), # Логику реализуем через FSM
        InlineKeyboardButton(text="🏠 В меню", callback_data="to_main")
    )
    return builder