from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    waiting_referral_code = State()
    waiting_phone = State()
    waiting_code = State()
    waiting_password = State()


class DeletedMessagesStates(StatesGroup):
    browsing = State()


class AnonymousRevealStates(StatesGroup):
    waiting_bot_username = State()


class UnregisterStates(StatesGroup):
    waiting_confirm = State()


class AdminStates(StatesGroup):
    waiting_user_id_details = State()
    waiting_user_id_delete = State()
    waiting_delete_confirm = State()
