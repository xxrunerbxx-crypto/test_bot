from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

from config import WEBAPP_BASE_URL

# Обновленное главное меню
def main_menu(portfolio_link: str, master_id: int):
    builder = InlineKeyboardBuilder()
    
    # ПУНКТ 5: Кнопка Записаться через Web App
    # ЗАМЕТКА: Если ты еще не захостил HTML-файл, замени 'web_app=...' на 'callback_data="start_booking"'
    # Но для работы Web App ссылка должна быть HTTPS
    builder.row(InlineKeyboardButton(
        text="💅 Записаться", 
        web_app=WebAppInfo(url=f"{WEBAPP_BASE_URL}/?role=client&master_id={master_id}")
    ))
    
    builder.row(InlineKeyboardButton(text="📋 Услуги", callback_data="services"))
    builder.row(InlineKeyboardButton(text="📸 Портфолио", url=portfolio_link))
    builder.row(InlineKeyboardButton(text="❌ Отменить мою запись", callback_data="cancel_booking"))
    builder.adjust(1)
    return builder.as_markup()

# ПУНКТ 3: Клавиатура для сбора отзывов (звездочки)
def review_kb(master_id: int):
    builder = InlineKeyboardBuilder()
    # Создаем 5 кнопок со звездами
    for i in range(1, 6):
        builder.add(InlineKeyboardButton(text=f"{i} ⭐", callback_data=f"rate_{master_id}_{i}"))
    builder.adjust(5) # Все звезды в один ряд
    return builder.as_markup()

def phone_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить свой номер", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )

def back_kb():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="to_main"))
    return builder.as_markup()