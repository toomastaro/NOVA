from aiogram import types, Router, F

from main_bot.handlers.user.menu import profile


async def choice(call: types.CallbackQuery):
    temp = call.data.split('|')
    await call.message.delete()

    if temp[1] == 'back':
        await profile(call.message)


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "Referral")
    return router
