from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    choosing_time = State()
    entering_name = State()
    entering_phone = State()


class MasterStates(StatesGroup):
    waiting_main = State()
    waiting_additional = State()
    waiting_warranty = State()
    waiting_photo = State()
    waiting_portfolio = State()


class OwnerAdminStates(StatesGroup):
    waiting_subscription_input = State()
    waiting_broadcast_text = State()
    waiting_broadcast_confirm = State()