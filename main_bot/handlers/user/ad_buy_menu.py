"""
Обработчики меню закупа рекламы.

Модуль предоставляет навигацию по разделам:
- Рекламные креативы
- Рекламные закупы
"""
import logging
from typing import Union

from aiogram import Router, F, types

from main_bot.keyboards import InlineAdCreative, InlineAdPurchase
from main_bot.keyboards.common import Reply
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Show Ad Buy Menu")
async def show_ad_buy_menu(event: Union[types.Message, types.CallbackQuery]) -> None:
    """
    Показать меню закупов с рекламными креативами и закупами.

    Аргументы:
        event (Union[types.Message, types.CallbackQuery]): Событие (сообщение или коллбек).
    """
    if isinstance(event, types.Message):
        await event.answer(
            "🛒 <b>Закуп</b>\n\nВыберите раздел:",
            reply_markup=InlineAdPurchase.ad_buy_main_menu(),
        )
    else:
        await event.message.edit_text(
            "🛒 <b>Закуп</b>\n\nВыберите раздел:",
            reply_markup=InlineAdPurchase.ad_buy_main_menu(),
        )


@safe_handler("Show Creatives")
async def show_creatives(call: types.CallbackQuery) -> None:
    """
    Показать меню рекламных креативов.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
    """
    await call.message.edit_text(
        "🎨 Рекламные креативы", reply_markup=InlineAdCreative.menu()
    )


@safe_handler("Show Purchases")
async def show_purchases(call: types.CallbackQuery) -> None:
    """
    Показать меню рекламных закупов.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
    """
    await call.message.edit_text(
        "💰 Рекламные закупы", reply_markup=InlineAdPurchase.menu()
    )


@safe_handler("Ad Buy Back To Main")
async def back_to_main(call: types.CallbackQuery) -> None:
    """
    Возврат в главное меню.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
    """
    await call.message.delete()
    await call.message.answer("Главное меню", reply_markup=Reply.menu())


def get_router() -> Router:
    """
    Регистрация роутера для меню закупа.

    Возвращает:
        Router: Роутер с зарегистрированными хендлерами.
    """
    router = Router(name="AdBuyMenu")
    router.message.register(show_ad_buy_menu, F.text == "🛒 Закуп")
    router.callback_query.register(show_ad_buy_menu, F.data == "AdBuyMenu|menu")
    router.callback_query.register(show_creatives, F.data == "AdBuyMenu|creatives")
    router.callback_query.register(show_purchases, F.data == "AdBuyMenu|purchases")
    router.callback_query.register(back_to_main, F.data == "AdBuyMenu|back")
    return router
