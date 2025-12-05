"""
Обработчики для меню подписки (баланс, подписка, реферальная система)
"""
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

from main_bot.keyboards.common import Reply


router = Router()


@router.callback_query(F.data.split("|")[0] == "MenuSubscription")
async def choice(call: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора в меню подписки"""
    temp = call.data.split('|')
    await call.message.delete()

    menu = {
        'balance': {
            'cor': show_balance_menu,
            'args': (call,)
        },
        'subscribe': {
            'cor': show_subscribe_menu,
            'args': (call, state,)
        },
        'referral': {
            'cor': show_referral_menu,
            'args': (call,)
        },
        'back': {
            'cor': back_to_main,
            'args': (call.message,)
        },
    }

    cor, args = menu[temp[1]].values()
    await cor(*args)


async def show_balance_menu(call: types.CallbackQuery):
    """Перенаправление на меню баланса из профиля"""
    from main_bot.handlers.user.profile.profile import show_balance
    from main_bot.database.db import db
    
    user = await db.get_user(user_id=call.from_user.id)
    await show_balance(call.message, user)


async def show_subscribe_menu(call: types.CallbackQuery, state: FSMContext):
    """Перенаправление на меню подписки из профиля"""
    from main_bot.handlers.user.profile.profile import show_subscribe
    await show_subscribe(call.message, state)


async def show_referral_menu(call: types.CallbackQuery):
    """Перенаправление на меню реферальной системы из профиля"""
    from main_bot.handlers.user.profile.profile import show_referral
    from main_bot.database.db import db
    
    user = await db.get_user(user_id=call.from_user.id)
    await show_referral(call.message, user)


async def back_to_main(message: types.Message):
    """Возврат в главное меню"""
    await message.answer(
        "Главное меню",
        reply_markup=Reply.menu()
    )
