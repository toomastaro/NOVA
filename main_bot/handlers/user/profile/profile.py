from aiogram import types, Router, F

from main_bot.database.db import db
from main_bot.database.user.model import User
from main_bot.keyboards import keyboards
from main_bot.utils.lang.language import text


async def choice(call: types.CallbackQuery, user: User):
    temp = call.data.split('|')
    await call.message.delete()

    menu = {
        'balance': {
            'cor': show_balance,
            'args': (call.message, user,)
        },
        'subscribe': {
            'cor': show_subscribe,
            'args': (call.message,)
        },
        'settings': {
            'cor': show_setting,
            'args': (call.message,)
        },
        'referral': {
            'cor': show_referral,
            'args': (call.message, user,)
        },
    }

    cor, args = menu[temp[1]].values()
    await cor(*args)


async def show_balance(message: types.Message, user: User):
    await message.answer(
        text("balance_text").format(
            user.balance
        ),
        reply_markup=keyboards.profile_balance()
    )


async def show_subscribe(message: types.Message):
    await message.answer(
        text("subscribe_text"),
        reply_markup=keyboards.profile_sub_choice()
    )


async def show_setting(message: types.Message):
    await message.answer(
        text("setting_text"),
        reply_markup=keyboards.profile_setting()
    )


async def show_referral(message: types.Message, user: User):
    referral_count = await db.get_count_user_referral(
        user_id=user.id
    )

    await message.answer(
        text('referral_text').format(
            referral_count,
            0,
            user.referral_earned,
            text('referral_url').format(
                (await message.bot.get_me()).username,
                user.id
            )
        ),
        reply_markup=keyboards.back(
            data='Referral|back'
        )
    )


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "MenuProfile")
    return router
