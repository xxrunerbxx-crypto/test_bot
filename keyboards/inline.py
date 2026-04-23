from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def main_menu(portfolio_link: str, master_id: int):
    """Основное меню клиента с компактной структурой"""
    builder = InlineKeyboardBuilder()
    # Основные действия (2 кнопки в ряду)
    builder.row(
        InlineKeyboardButton(text="💅 Записаться", callback_data="start_booking"),
        InlineKeyboardButton(text="📅 Мои записи", callback_data="my_bookings"),
    )
    # Информация (2 кнопки в ряду)
    builder.row(
        InlineKeyboardButton(text="📋 Услуги", callback_data="services"),
        InlineKeyboardButton(text="📸 Портфолио", url=portfolio_link),
    )
    # Обратная связь (2 кнопки в ряду)
    builder.row(
        InlineKeyboardButton(text="💡 Предложение", callback_data="feedback_suggestion"),
        InlineKeyboardButton(text="🐞 Ошибка", callback_data="feedback_bug"),
    )
    # Управление записью (1 кнопка)
    builder.row(InlineKeyboardButton(text="❌ Отменить запись", callback_data="cancel_booking"))
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def info_menu(portfolio_link: str, master_id: int):
    """Меню информации (услуги, портфолио)"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📋 Услуги", callback_data="services"))
    builder.row(InlineKeyboardButton(text="📸 Портфолио", url=portfolio_link))
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="to_main"))
    return builder.as_markup()


def review_kb(master_id: int, booking_id: int):
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.add(InlineKeyboardButton(text=f"{i} ⭐", callback_data=f"rate_{master_id}_{booking_id}_{i}"))
    builder.adjust(5)
    return builder.as_markup()


def phone_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить свой номер", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )


def back_kb():
    """Кнопка назад в главное меню"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="to_main"))
    return builder.as_markup()


def error_back_kb():
    """Кнопка назад после ошибки"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Вернуться в главное меню", callback_data="to_main"))
    return builder.as_markup()
