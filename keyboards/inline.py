from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def main_menu(portfolio_link: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💅 Записаться", callback_data="start_booking"))
    builder.row(InlineKeyboardButton(text="📋 Услуги", callback_data="services"))
    builder.row(InlineKeyboardButton(text="📸 Портфолио", url=portfolio_link))
    builder.row(InlineKeyboardButton(text="❌ Отменить запись", callback_data="cancel_booking"))
    return builder.as_markup()

# Клавиатура с кнопкой авто-отправки номера

def phone_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить номер (авто)", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def back_kb():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="to_main"))
    return builder.as_markup()

# --- НОВАЯ КЛАВИАТУРА ДЛЯ ТЕЛЕФОНА ---
def phone_kb():
    # Создаем обычную (Reply) клавиатуру с кнопкой запроса контакта
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить свой номер", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )