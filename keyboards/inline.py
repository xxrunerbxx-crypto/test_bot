from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

def main_menu(portfolio_link: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💅 Записаться", callback_data="start_booking"))
    builder.row(InlineKeyboardButton(text="📋 Услуги", callback_data="services"))
    
    # Прямая ссылка на портфолио
    builder.row(InlineKeyboardButton(text="📸 Портфолио", url=portfolio_link))
    
    builder.row(InlineKeyboardButton(text="❌ Отменить запись", callback_data="cancel_booking"))
    return builder.as_markup()

def back_kb():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="to_main"))
    return builder.as_markup()

def nav_btns():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_step"),
        InlineKeyboardButton(text="🏠 В меню", callback_data="to_main")
    )
    return builder