import os

from aiogram import types, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import Config
from main_bot.database.db import db
from main_bot.keyboards.keyboards import keyboards
from main_bot.states.admin import Promo
from main_bot.utils.lang.language import text


async def admin_menu(message: types.Message):
    if message.from_user.id not in Config.ADMINS:
        return

    await message.answer(
        'Админ меню',
        reply_markup=keyboards.admin()
    )


async def choice(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')

    if temp[1] == 'session':
        session_count = len(os.listdir("main_bot/utils/sessions/"))
        await call.message.edit_text(
            "Доступно сессий: {}".format(session_count),
            reply_markup=keyboards.admin_sessions()
        )

    if temp[1] == "promo":
        await call.message.edit_text(
            'Отправьте данные для промокода:\n\n'
            'Имя промокода\n'
            'Сумма баланса (0, если не нужно)\n'
            'Количество использований\n'
            'Сумма скидки в % (0, если не нужно)',
            reply_markup=keyboards.back(
                data="AdminPromoBack"
            )
        )
        await state.set_state(Promo.input)

    return await call.answer()

    if temp[1] == "mail":
        pass

    if temp[1] == "stats":
        await call.message.edit_text(
            text("main:stats").format(

            )
        )

    if temp[1] == "ads":
        pass

    # if temp[1] == 'mail':
    #     await call.message.edit_text(
    #         'Меню рассылки',
    #         reply_markup=Keyboards.admin_mail()
    #     )
    #
    # if temp[1] == 'ads':
    #     await call.message.edit_text(
    #         'Рекламные ссылки:',
    #         reply_markup=Keyboards.admin_ads()
    #     )


def hand_add():
    router = Router()
    router.message.register(admin_menu, Command('admin'))
    router.callback_query.register(choice, F.data.split('|')[0] == "Admin")
    return router
