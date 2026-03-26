from aiogram.fsm.state import State, StatesGroup

class BookingStates(StatesGroup):
    choosing_date = State()
    choosing_time = State()
    entering_name = State()
    entering_phone = State()

class AdminStates(StatesGroup):
    adding_time = State()
    viewing_date = State()
    waiting_portfolio = State() # Состояние для ожидания ссылки
    waiting_subscription_input = State() # Для ввода "master_id days" в админке
    waiting_broadcast_text = State() # Для ввода текста рассылки всем пользователям
    waiting_broadcast_confirm = State() # Подтверждение рассылки

class ServiceStates(StatesGroup):
    waiting_main = State()
    waiting_additional = State()
    waiting_warranty = State()
    waiting_photo = State()  