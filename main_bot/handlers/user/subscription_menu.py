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
        'top_up': {
            'cor': show_top_up_menu,
            'args': (call, state,)
        },
        'subscribe': {
            'cor': show_subscribe_menu,
            'args': (call, state,)
        },
        'referral': {
            'cor': show_referral_menu,
            'args': (call,)
        },
        'align_sub': {
            'cor': show_align_sub_menu,
            'args': (call, state,)
        },
        'transfer_sub': {
            'cor': show_transfer_sub_menu,
            'args': (call, state,)
        },
        'back': {
            'cor': back_to_main,
            'args': (call.message,)
        },
    }

    cor, args = menu[temp[1]].values()
    await cor(*args)


async def show_top_up_menu(call: types.CallbackQuery, state: FSMContext):
    """Показать меню пополнения баланса"""
    from main_bot.handlers.user.profile.balance import show_top_up
    await show_top_up(call.message, state)


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


async def show_align_sub_menu(call: types.CallbackQuery, state: FSMContext):
    """Показать меню выравнивания подписки"""
    from main_bot.database.db import db
    from main_bot.keyboards import keyboards
    from main_bot.utils.lang.language import text
    
    user = await db.get_user(user_id=call.from_user.id)
    sub_objects = await db.get_subscribe_channels(
        user_id=user.id
    )

    if len(sub_objects) < 2:
        return await call.answer(
            text("error_align_sub"),
            show_alert=True
        )

    await state.update_data(
        align_chosen=[]
    )

    await call.message.delete()
    await call.message.answer(
        text("align_sub"),
        reply_markup=keyboards.align_sub(
            sub_objects=sub_objects,
            chosen=[]
        )
    )


async def show_transfer_sub_menu(call: types.CallbackQuery, state: FSMContext):
    """Показать меню переноса подписки"""
    from main_bot.handlers.user.profile.transfer_subscription import show_transfer_sub_menu as transfer_menu
    await transfer_menu(call, state)


async def back_to_main(message: types.Message):
    """Возврат в главное меню"""
    await message.answer(
        "Главное меню",
        reply_markup=Reply.menu()
    )
