from aiogram.fsm.state import State, StatesGroup


class Promo(StatesGroup):
    input = State()


class Session(StatesGroup):
    phone = State()
    code = State()
