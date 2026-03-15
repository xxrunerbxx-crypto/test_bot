from aiogram.fsm.state import State, StatesGroup

class AdminStates(StatesGroup):
    adding_slot_date = State()
    adding_slot_time = State()
    broadcasting = State()
    setting_services = State()
    setting_portfolio = State()

class BookingStates(StatesGroup):
    choosing_date = State()
    choosing_time = State()
    entering_name = State()
    entering_phone = State()