import logging
from aiogram import Router, types
from aiogram.filters import CommandStart

from config import settings
from main_bot.keyboards.keyboards import keyboards
from main_bot.utils.lang.language import text
from main_bot.utils.middlewares import StartMiddle

logger = logging.getLogger(__name__)






async def start(message: types.Message):
    await message.answer(
        text("start_text") + f"\n\n<code>v{settings.VERSION}</code>",
        reply_markup=keyboards.menu(),
    )


def hand_add():
    router = Router()
    router.message.middleware(StartMiddle())
    router.message.register(start, CommandStart())
    return router
