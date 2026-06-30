from aiogram.fsm.state import State, StatesGroup


class AutomationStates(StatesGroup):
    schedule_peer = State()
    schedule_text = State()
    schedule_time = State()
    reminder_text = State()
    reminder_time = State()
