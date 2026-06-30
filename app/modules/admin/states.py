from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    waiting_user_id_details = State()
    waiting_user_id_delete = State()
    waiting_delete_confirm = State()
