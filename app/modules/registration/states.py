from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    waiting_referral_code = State()
    waiting_phone = State()
    waiting_code = State()
    waiting_password = State()


class UnregisterStates(StatesGroup):
    waiting_confirm = State()
