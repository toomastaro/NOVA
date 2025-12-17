"""
Состояния FSM для hello_bot.
"""

from aiogram.fsm.state import State, StatesGroup


class Answer(StatesGroup):
    """Состояния для настройки автоответов."""

    message = State()
    keyword = State()


class Hello(StatesGroup):
    """Состояния для настройки приветствия."""

    message = State()


class Bye(StatesGroup):
    """Состояния для настройки прощания."""

    message = State()


class Application(StatesGroup):
    """Состояния для настройки заявок."""

    delay = State()
