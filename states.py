from aiogram.fsm.state import State, StatesGroup

class BookingStates(StatesGroup):
    """Состояния для процесса записи клиента"""
    choosing_date = State()    # Выбор даты в календаре
    choosing_time = State()    # Выбор конкретного времени
    entering_name = State()    # Ввод имени
    entering_phone = State()   # Ввод телефона

class AdminStates(StatesGroup):
    """Состояния для панели управления мастера"""
    waiting_for_new_password = State() # СОЗДАНИЕ пароля (самый первый запуск)
    waiting_for_password = State()     # ВВОД пароля (для обычного входа)
    
    adding_slot_date = State()         # Выбор даты для новых окон
    adding_slot_time = State()         # Ввод времени для новых окон
    
    filling_main_services = State()    # Настройка основных услуг
    filling_add_services = State()     # Настройка доп. услуг
    filling_warranty = State()         # Настройка гарантии
    
    setting_portfolio = State()        # Настройка ссылки на портфолио
    view_schedule_date = State()       # Ввод даты для просмотра записей
    broadcast_message = State()        # Ввод текста для рассылки всем
    deleting_slot_date = State()       # Выбор даты для удаления окон