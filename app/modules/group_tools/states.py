from aiogram.fsm.state import State, StatesGroup


class GroupToolsStates(StatesGroup):
    track_add = State()
    track_remove = State()
    group_add = State()
    group_remove = State()
