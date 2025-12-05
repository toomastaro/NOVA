from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.states.admin import Promo


async def back(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        'Админ меню',
        reply_markup=keyboards.admin()
    )


async def get_promo(message: types.Message, state: FSMContext):
    temp = message.text.split('\n')
    if len(temp) < 4:
        return await message.answer(
            'Что-то забыл указать'
        )

    name = temp[0]
    exist = await db.get_promo(name)
    if exist:
        return await message.answer("Уже существует")

    try:
        amount = int(temp[1]) if int(temp[1]) > 0 else None
        count_use = int(temp[2])
        discount = int(temp[3]) if int(temp[3]) > 0 else None
    except ValueError:
        return await message.answer(
            '❌ Количественные значения должны быть цифрой или числом'
        )

    await db.add_promo(
        name=name,
        amount=amount,
        use_count=count_use,
        discount=discount
    )

    await state.clear()
    await message.answer(
        'Промокод был успешно добавлен'
    )


def hand_add():
    router = Router()
    router.message.register(get_promo, Promo.input, F.text)
    router.callback_query.register(back, F.data.split('|')[0] == "AdminPromoBack")
    return router
