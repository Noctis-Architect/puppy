from aiogram.fsm.state import State, StatesGroup


class DeletedMessagesStates(StatesGroup):
    browsing = State()
