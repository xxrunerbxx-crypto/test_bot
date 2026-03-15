import calendar
from datetime import datetime
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from database.db import db

def generate_calendar(year: int, month: int, is_admin: bool = False):
    builder = InlineKeyboardBuilder()
    
    # Заголовок: Месяц и Год
    month_name = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", 
                  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"][month-1]
    builder.row(InlineKeyboardButton(text=f"{month_name} {year}", callback_data="ignore"))

    # Дни недели
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    builder.row(*[InlineKeyboardButton(text=d, callback_data="ignore") for d in days])

    # Получаем данные о слотах из БД
    month_str = f"{year}-{month:02d}"
    available_slots = db.get_slots_count_by_month(month_str)

    month_calendar = calendar.monthcalendar(year, month)
    for week in month_calendar:
        row_buttons = []
        for day in week:
            if day == 0:
                row_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                count = available_slots.get(date_str, 0)
                
                if is_admin:
                    # Админ видит все дни, где есть хоть какие-то слоты
                    text = f"{day} (•)" if count > 0 else f"{day}"
                    row_buttons.append(InlineKeyboardButton(text=text, callback_data=f"admin_date_{date_str}"))
                else:
                    # Пользователь видит число, если есть слоты, иначе прочерк
                    if count > 0:
                        row_buttons.append(InlineKeyboardButton(text=str(day), callback_data=f"user_date_{date_str}"))
                    else:
                        row_buttons.append(InlineKeyboardButton(text="-", callback_data="ignore"))
        builder.row(*row_buttons)

    # Навигация внизу
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="to_main"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="to_main")
    )
    return builder.as_markup()