"""
Обработчики для меню подписки (баланс, подписка, реферальная система)
"""

import logging
import time

from aiogram import F, types, Router
from aiogram.fsm.context import FSMContext

from main_bot.keyboards.common import Reply
from main_bot.keyboards import keyboards
from main_bot.utils.error_handler import safe_handler
from main_bot.utils.lang.language import text
from main_bot.database.db import db
from main_bot.handlers.user.profile.balance import show_top_up
from main_bot.handlers.user.profile.profile import show_subscribe, show_referral
from main_bot.handlers.user.profile.transfer_subscription import (
    show_transfer_sub_menu as transfer_menu,
)
from main_bot.handlers.user.profile.info import show_info_menu as info_menu

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data.split("|")[0] == "MenuSubscription")
@safe_handler("Subscription Menu Choice")
async def choice(call: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора в меню подписки"""
    temp = call.data.split("|")
    await call.message.delete()

    menu = {
        "top_up": {
            "cor": show_top_up_menu,
            "args": (
                call,
                state,
            ),
        },
        "subscribe": {
            "cor": show_subscribe_menu,
            "args": (
                call,
                state,
            ),
        },
        "referral": {"cor": show_referral_menu, "args": (call,)},
        "align_sub": {
            "cor": show_align_sub_menu,
            "args": (
                call,
                state,
            ),
        },
        "transfer_sub": {
            "cor": show_transfer_sub_menu,
            "args": (
                call,
                state,
            ),
        },
        "info": {"cor": show_info_menu, "args": (call,)},
        "back": {"cor": back_to_main, "args": (call.message,)},
    }

    handler_data = menu[temp[1]]
    await handler_data["cor"](*handler_data["args"])


@safe_handler("Show Top Up Menu")
async def show_top_up_menu(call: types.CallbackQuery, state: FSMContext):
    """Показать меню пополнения баланса"""
    await show_top_up(call.message, state)


@safe_handler("Show Subscribe Menu")
async def show_subscribe_menu(call: types.CallbackQuery, state: FSMContext):
    """Перенаправление на меню подписки из профиля"""
    await show_subscribe(call.message, state)


@safe_handler("Show Referral Menu")
async def show_referral_menu(call: types.CallbackQuery):
    """Перенаправление на меню реферальной системы из профиля"""
    user = await db.user.get_user(user_id=call.from_user.id)
    await show_referral(call.message, user)


@safe_handler("Show Align Sub Menu")
async def show_align_sub_menu(call: types.CallbackQuery, state: FSMContext):
    """Показать меню выравнивания подписки"""
    user = await db.user.get_user(user_id=call.from_user.id)
    all_sub_objects = await db.channel.get_subscribe_channels(user_id=user.id)

    now = int(time.time())
    sub_objects = [ch for ch in all_sub_objects if ch.subscribe and ch.subscribe > now]

    if len(sub_objects) < 2:
        return await call.answer(text("error_align_sub"), show_alert=True)

    await state.update_data(align_chosen=[])

    await call.message.answer(
        text("align_sub"),
        reply_markup=keyboards.align_sub(sub_objects=sub_objects, chosen=[]),
    )


@safe_handler("Show Transfer Sub Menu")
async def show_transfer_sub_menu(call: types.CallbackQuery, state: FSMContext):
    """Показать меню переноса подписки"""
    await transfer_menu(call, state)


@safe_handler("Show Info Menu")
async def show_info_menu(call: types.CallbackQuery):
    """Показать меню информации"""
    await info_menu(call)


@safe_handler("Subscription Back To Main")
async def back_to_main(message: types.Message):
    """Возврат в главное меню"""
    await message.answer("Главное меню", reply_markup=Reply.menu())


def get_router():
    """Возвращает роутер модуля."""
    return router
