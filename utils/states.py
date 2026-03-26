from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    choosing_time = State()
    entering_name = State()
    entering_phone = State()


class MasterStates(StatesGroup):
    choosing_services_mode = State()
    waiting_main = State()
    waiting_additional = State()
    waiting_warranty = State()
    waiting_photo = State()
    waiting_price_photo = State()
    waiting_portfolio = State()
    waiting_custom_slot = State()


class OwnerAdminStates(StatesGroup):
    waiting_subscription_input = State()
    waiting_broadcast_text = State()
    waiting_broadcast_confirm = State()