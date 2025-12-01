from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from utils.middleware import SetCrud, ErrorMiddleware  # AnswerMiddleware
from .user import get_router as user_router


def set_routers():
    dp = Dispatcher(
        storage=MemoryStorage()
    )
    dp.update.middleware.register(
        SetCrud()
    )
    # dp.update.middleware.register(
    #     AnswerMiddleware()
    # )
    dp.update.middleware.register(
        ErrorMiddleware()
    )
    dp.include_routers(
        user_router()
    )
    return dp
