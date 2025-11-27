from aiogram import F, Router, types

from hello_bot.keyboards.keyboards import keyboards
from hello_bot.utils.lang.language import text


async def choice(call: types.CallbackQuery):
    await call.message.edit_text(text("start_text"), reply_markup=keyboards.menu())


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "StatsBack")
    return router
