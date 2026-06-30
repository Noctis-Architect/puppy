from aiogram.fsm.state import State, StatesGroup


class AnonymousRevealStates(StatesGroup):
    waiting_bot_username = State()
