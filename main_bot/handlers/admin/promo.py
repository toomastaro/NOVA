"""
Модуль управления промокодами.

Содержит:
- Создание новых промокодов
- Валидацию параметров промокода
"""

import logging
from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.states.admin import Promo
from main_bot.utils.lang.language import text
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Admin Promo Back")
async def back(call: types.CallbackQuery, state: FSMContext):
    """Возврат в меню админа."""
    await state.clear()
    await call.message.edit_text("Админ меню", reply_markup=keyboards.admin())


@safe_handler("Admin Get Promo")
async def get_promo(message: types.Message, state: FSMContext):
    """
    Создание нового промокода.
    Формат ввода: Название\nКоличество\nКол-во использований\nСкидка
    """
    temp = message.text.split("\n")
    if len(temp) < 4:
        return await message.answer(text("promo:error:args"))

    name = temp[0]
    exist = await db.promo.get_promo(name)
    if exist:
        return await message.answer(text("promo:error:exist"))

    try:
        amount = int(temp[1]) if int(temp[1]) > 0 else None
        count_use = int(temp[2])
        discount = int(temp[3]) if int(temp[3]) > 0 else None
    except ValueError:
        return await message.answer(text("promo:error:digit"))

    await db.promo.add_promo(
        name=name, amount=amount, use_count=count_use, discount=discount
    )

    logger.info(
        f"Admin {message.from_user.id} created promo '{name}' (amount={amount}, uses={count_use}, discount={discount})"
    )

    await state.clear()
    await message.answer(text("promo:success:add"))


def get_router():
    """Регистрация роутера для управления промокодами."""
    router = Router()
    router.message.register(get_promo, Promo.input, F.text)
    router.callback_query.register(back, F.data.split("|")[0] == "AdminPromoBack")
    return router
