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
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler(
    "Закуп: показ меню"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_ad_buy_menu(event: Union[types.Message, types.CallbackQuery]) -> None:
    """
    Показать меню закупов с рекламными креативами и закупами.
    Требуется наличие хотя бы одного канала с активной подпиской.

    Аргументы:
        event (Union[types.Message, types.CallbackQuery]): Событие (сообщение или коллбек).
    """
    # Импортируем для проверки подписки
    from main_bot.database.db import db
    from main_bot.utils.lang.language import text

    # Проверка наличия каналов с активной подпиской
    user_id = event.from_user.id
    channels = await db.channel.get_user_channels(user_id=user_id, limit=500)
    channels_with_sub = [ch for ch in channels if ch.subscribe]

    if not channels_with_sub:
        error_text = text("error_no_subscription_ad_buy")
        if isinstance(event, types.Message):
            return await event.answer(error_text)
        else:
            return await event.answer(error_text, show_alert=True)

    # Показ меню закупов
    menu_text = text("ad_buy_menu:title")
    if isinstance(event, types.Message):
        await event.answer(
            menu_text,
            reply_markup=InlineAdPurchase.ad_buy_main_menu(),
        )
        # Удаляем сообщение пользователя ("🛒 Закуп"), чтобы оно не спамило в чате
        try:
            await event.delete()
        except Exception:
            pass
    else:
        await event.message.edit_text(
            menu_text,
            reply_markup=InlineAdPurchase.ad_buy_main_menu(),
        )


@safe_handler(
    "Закуп: показ креативов"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_creatives(call: types.CallbackQuery) -> None:
    """
    Показать меню рекламных креативов.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
    """
    await call.message.edit_text(
        "🎨 Рекламные креативы", reply_markup=InlineAdCreative.menu()
    )


@safe_handler(
    "Закуп: показ закупов"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_purchases(call: types.CallbackQuery) -> None:
    """
    Показать меню рекламных закупов.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
    """
    await call.message.edit_text(
        "💰 Рекламные закупы", reply_markup=InlineAdPurchase.menu()
    )


@safe_handler(
    "Закуп: возврат в главное меню"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def back_to_main(call: types.CallbackQuery) -> None:
    """
    Возврат в главное меню.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
    """
    await call.message.delete()
    await call.message.answer("Главное меню", reply_markup=Reply.menu(call.from_user.id))


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
