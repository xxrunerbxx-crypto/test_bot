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

def admin_menu():
    kb = [
        [InlineKeyboardButton(text="📅 Посмотреть записи", callback_data="admin_view_schedule")],
        [InlineKeyboardButton(text="⏰ Добавить слоты", callback_data="admin_add_slot")],
        [InlineKeyboardButton(text="🗑 Удалить окна", callback_data="admin_delete_slots")], 
        [InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="admin_broadcast")], 
        [InlineKeyboardButton(text="💸 Настроить прайс", callback_data="admin_setup_services")],
        [InlineKeyboardButton(text="🖼 Ссылка на портфолио", callback_data="admin_set_portfolio")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

async def generate_calendar(month: int, year: int, available_dates: list, is_admin=False):
    """
    Генерирует календарь. 
    Если is_admin=True, то все даты кликабельны.
    Если is_admin=False, кликабельны только даты из available_dates.
    """
    builder = InlineKeyboardBuilder()
    months_names = {1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
                    7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"}
    
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
                # В режиме админа все кнопки активны, в режиме юзера - только те что в базе
                if is_admin or date_str in available_dates:
                    row.append(InlineKeyboardButton(text=str(day), callback_data=f"date_{date_str}"))
                else:
                    row.append(InlineKeyboardButton(text="-", callback_data="ignore"))
        builder.row(*row)
    
    builder.row(InlineKeyboardButton(text="🏠 В меню", callback_data="to_main"))
    return builder.as_markup()

def admin_time_templates():
    """Кнопки быстрого выбора времени для мастера"""
    kb = [
        [InlineKeyboardButton(text="🌅 Утро (9:00, 11:00, 13:00)", callback_data="tpl_morning")],
        [InlineKeyboardButton(text="☀️ День (14:00, 16:00, 18:00)", callback_data="tpl_afternoon")],
        [InlineKeyboardButton(text="🌙 Вечер (19:00, 21:00)", callback_data="tpl_evening")],
        [InlineKeyboardButton(text="📅 Весь день (шаблон)", callback_data="tpl_fullday")],
        [InlineKeyboardButton(text="🏠 Отмена", callback_data="admin_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)
# кнопка назад в меню из портфолио и услуг
def back_to_main():
    """Кнопка возврата в главное меню для пользователя"""
    kb = [
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)