from aiogram.fsm.state import State, StatesGroup


class Answer(StatesGroup):
    message = State()
    keyword = State()


class Hello(StatesGroup):
    message = State()


class Bye(StatesGroup):
    message = State()


class Application(StatesGroup):
    delay = State()
