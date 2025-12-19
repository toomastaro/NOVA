from aiogram.fsm.state import State, StatesGroup


class Promo(StatesGroup):
    input = State()


class Session(StatesGroup):
    pool_select = State()
    phone = State()
    code = State()


class AdminChannels(StatesGroup):
    searching = State()


class AdminMailing(StatesGroup):
    post = State()
    confirm = State()
