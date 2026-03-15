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

class ServiceStates(StatesGroup):
    waiting_main = State()
    waiting_additional = State()
    waiting_warranty = State()