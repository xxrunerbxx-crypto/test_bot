import calendar
from datetime import datetime, date
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from database.db import db

def generate_calendar(year: int, month: int, master_id: int, is_admin: bool = False):
    """
    Генерация инлайн-календаря.
    :param year: Год
    :param month: Месяц
    :param master_id: ID мастера, чьи слоты мы проверяем
    :param is_admin: Если True — это режим управления для мастера
    """
    builder = InlineKeyboardBuilder()
    
    # Заголовок: Месяц и Год
    month_names = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", 
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    builder.row(InlineKeyboardButton(text=f"{month_names[month-1]} {year}", callback_data="ignore"))

    # Дни недели
    days_abbr = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    builder.row(*[InlineKeyboardButton(text=d, callback_data="ignore") for d in days_abbr])

    # Получаем данные о слотах КОНКРЕТНОГО мастера из БД
    month_str = f"{year}-{month:02d}"
    # Теперь мы передаем master_id в запрос
    available_slots = db.get_slots_count_by_month(master_id, month_str)

    month_calendar = calendar.monthcalendar(year, month)
    
    today = date.today()
    for week in month_calendar:
        row_buttons = []
        for day in week:
            if day == 0:
                # Пустые ячейки (дни другого месяца)
                row_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                count = available_slots.get(date_str, 0)
                day_obj = date(year, month, day)
                
                if day_obj < today:
                    row_buttons.append(InlineKeyboardButton(text="-", callback_data="ignore"))
                elif is_admin:
                    text = f"{day} ({count})" if count > 0 else f"{day}"
                    row_buttons.append(InlineKeyboardButton(text=text, callback_data=f"admin_date_{date_str}"))
                else:
                    if count > 0:
                        row_buttons.append(InlineKeyboardButton(text=str(day), callback_data=f"user_date_{date_str}"))
                    else:
                        row_buttons.append(InlineKeyboardButton(text="-", callback_data="ignore"))
        builder.row(*row_buttons)

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    mode = "admin" if is_admin else "user"
    builder.row(
        InlineKeyboardButton(text="⬅️", callback_data=f"cal_{mode}_{master_id}_{prev_year}_{prev_month}"),
        InlineKeyboardButton(text="➡️", callback_data=f"cal_{mode}_{master_id}_{next_year}_{next_month}"),
    )

    back_callback = "m_main" if is_admin else "to_main"
    builder.row(InlineKeyboardButton(text="🏠 В главное меню", callback_data=back_callback))
    
    return builder.as_markup()