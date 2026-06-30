from aiogram.fsm.state import State, StatesGroup


class MemorySearchStates(StatesGroup):
    waiting_query = State()
    waiting_profile_id = State()
    waiting_export_id = State()
