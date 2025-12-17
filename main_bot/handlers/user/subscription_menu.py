"""
Обработчики для меню подписки (баланс, подписка, реферальная система).

Модуль управляет:
- Навигацией по меню подписки
- Отображением баланса и пополнения
- Меню выравнивания сроков подписок
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
async def choice(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик выбора в меню подписки.
    Маршрутизирует запросы к соответствующим подменю.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
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

    if temp[1] in menu:
        handler_data = menu[temp[1]]
        await handler_data["cor"](*handler_data["args"])
    else:
        logger.warning(f"Неизвестное действие меню подписки: {temp[1]}")


@safe_handler("Show Top Up Menu")
async def show_top_up_menu(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Показать меню пополнения баланса.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    await show_top_up(call.message, state)


@safe_handler("Show Subscribe Menu")
async def show_subscribe_menu(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Перенаправление на меню подписки из профиля.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    await show_subscribe(call.message, state)


@safe_handler("Show Referral Menu")
async def show_referral_menu(call: types.CallbackQuery) -> None:
    """
    Перенаправление на меню реферальной системы из профиля.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
    """
    user = await db.user.get_user(user_id=call.from_user.id)
    await show_referral(call.message, user)


@safe_handler("Show Align Sub Menu")
async def show_align_sub_menu(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Показать меню выравнивания подписки.
    Позволяет синхронизировать даты окончания подписок разных каналов.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
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
async def show_transfer_sub_menu(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Показать меню переноса подписки.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    await transfer_menu(call, state)


@safe_handler("Show Info Menu")
async def show_info_menu(call: types.CallbackQuery) -> None:
    """
    Показать меню информации.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
    """
    await info_menu(call)


@safe_handler("Subscription Back To Main")
async def back_to_main(message: types.Message) -> None:
    """
    Возврат в главное меню.

    Аргументы:
        message (types.Message): Сообщение пользователя.
    """
    await message.answer("Главное меню", reply_markup=Reply.menu())


def get_router() -> Router:
    """
    Возвращает роутер модуля.

    Возвращает:
        Router: Роутер с зарегистрированными хендлерами.
    """
    return router
