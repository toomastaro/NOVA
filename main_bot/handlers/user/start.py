from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart

from config import Config
from main_bot.keyboards.keyboards import keyboards
from main_bot.utils.lang.language import text
from main_bot.utils.middlewares import StartMiddle


async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        text("start_text") + f"\n\nVersion: {Config.VERSION}",
        reply_markup=keyboards.menu()
    )


def hand_add():
    router = Router()
    router.message.middleware(StartMiddle())
    router.message.register(start, CommandStart())
    return router
