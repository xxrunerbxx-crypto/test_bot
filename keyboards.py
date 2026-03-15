import calendar
from datetime import datetime
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_admin_main_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить окна", callback_data="adm_add"))
    builder.row(InlineKeyboardButton(text="🗑 Удалить окна", callback_data="adm_del"))
    builder.row(InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_msg"))
    builder.row(InlineKeyboardButton(text="⚙️ Услуги", callback_data="adm_serv"),
                InlineKeyboardButton(text="🖼 Портфолио", callback_data="adm_port"))
    return builder.as_markup()

def admin_time_templates():
    kb = [
        [InlineKeyboardButton(text="🌅 Утро (9:00, 11:00, 13:00)", callback_data="tpl_9,11,13")],
        [InlineKeyboardButton(text="☀️ День (14:00, 16:00, 18:00)", callback_data="tpl_14,16,18")],
        [InlineKeyboardButton(text="🌙 Вечер (19:00, 21:00)", callback_data="tpl_19,21")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="adm_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

async def generate_calendar(month: int, year: int, available_dates: list, is_admin=False):
    builder = InlineKeyboardBuilder()
    months = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    builder.row(InlineKeyboardButton(text=f"{months[month]} {year}", callback_data="ignore"))
    
    for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]:
        builder.button(text=day, callback_data="ignore")
    
    month_days = calendar.monthcalendar(year, month)
    for week in month_days:
        for day in week:
            if day == 0:
                builder.button(text=" ", callback_data="ignore")
            else:
                d_str = f"{day:02d}.{month:02d}"
                if is_admin or d_str in available_dates:
                    builder.button(text=str(day), callback_data=f"date_{d_str}")
                else:
                    builder.button(text="-", callback_data="ignore")
    
    builder.adjust(7)
    builder.row(InlineKeyboardButton(text="🏠 В меню", callback_data="adm_main" if is_admin else "to_main"))
    return builder.as_markup()

def get_admin_cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ В меню", callback_data="adm_main")]])