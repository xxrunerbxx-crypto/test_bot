import calendar
from datetime import datetime
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_menu():
    kb = [
        [InlineKeyboardButton(text="💅 Записаться", callback_data="start_booking")],
        [InlineKeyboardButton(text="📅 Моя запись", callback_data="my_booking")],
        [InlineKeyboardButton(text="📜 Услуги и цены", callback_data="show_services"),
         InlineKeyboardButton(text="📸 Портфолио", callback_data="show_portfolio")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

# Главное меню админа (новое)
def get_admin_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить окна", callback_data="admin_add_slot")
    builder.button(text="🗑 Удалить окна", callback_data="admin_delete_slots")
    builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.button(text="⚙️ Услуги", callback_data="admin_setup_services")
    builder.button(text="🖼 Ссылка на портфолио", callback_data="admin_set_portfolio")
    builder.adjust(2)
    return builder.as_markup()

# Клавиатура выбора даты для УДАЛЕНИЯ
def get_admin_delete_dates_kb(dates):
    builder = InlineKeyboardBuilder()
    for date in dates:
        builder.button(text=f"📅 {date}", callback_data=f"del_date_{date}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="❌ В главное меню", callback_data="admin_main_menu"))
    return builder.as_markup()

# Универсальная кнопка "Отмена"
def get_admin_cancel_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена / В меню", callback_data="admin_main_menu")
    return builder.as_markup()

def back_to_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="to_main")]
    ])

def admin_time_templates():
    kb = [
        [InlineKeyboardButton(text="🌅 Утро (9:00, 11:00, 13:00)", callback_data="tpl_morning")],
        [InlineKeyboardButton(text="☀️ День (14:00, 16:00, 18:00)", callback_data="tpl_afternoon")],
        [InlineKeyboardButton(text="🌙 Вечер (19:00, 21:00)", callback_data="tpl_evening")],
        [InlineKeyboardButton(text="📅 Весь день", callback_data="tpl_fullday")],
        [InlineKeyboardButton(text="🏠 Отмена", callback_data="admin_main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

async def generate_calendar(month: int, year: int, available_dates: list, is_admin=False):
    builder = InlineKeyboardBuilder()
    months_names = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
        7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }
    builder.row(InlineKeyboardButton(text=f"{months_names[month]} {year}", callback_data="ignore"))
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    builder.row(*[InlineKeyboardButton(text=d, callback_data="ignore") for d in week_days])
    month_calendar = calendar.monthcalendar(year, month)
    for week in month_calendar:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                date_str = f"{day:02d}.{month:02d}"
                if is_admin or date_str in available_dates:
                    row.append(InlineKeyboardButton(text=str(day), callback_data=f"date_{date_str}"))
                else:
                    row.append(InlineKeyboardButton(text="-", callback_data="ignore"))
        builder.row(*row)
    builder.row(InlineKeyboardButton(text="🏠 В меню", callback_data="to_main"))
    return builder.as_markup()
