import logging
from aiogram import Router, F, types

from main_bot.keyboards import InlineAdCreative, InlineAdPurchase
from main_bot.keyboards.common import Reply
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Show Ad Buy Menu")
async def show_ad_buy_menu(event: types.Message | types.CallbackQuery):
    """Показать меню закупов с рекламными креативами и закупами"""
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
async def show_creatives(call: types.CallbackQuery):
    """Показать меню рекламных креативов"""
    await call.message.edit_text(
        "🎨 Рекламные креативы", reply_markup=InlineAdCreative.menu()
    )


@safe_handler("Show Purchases")
async def show_purchases(call: types.CallbackQuery):
    """Показать меню рекламных закупов"""
    await call.message.edit_text(
        "💰 Рекламные закупы", reply_markup=InlineAdPurchase.menu()
    )


@safe_handler("Ad Buy Back To Main")
async def back_to_main(call: types.CallbackQuery):
    """Возврат в главное меню"""
    await call.message.delete()
    await call.message.answer("Главное меню", reply_markup=Reply.menu())


def get_router():
    """Регистрация роутера для меню закупа"""
    router = Router(name="AdBuyMenu")
    router.message.register(show_ad_buy_menu, F.text == "🛒 Закуп")
    router.callback_query.register(show_ad_buy_menu, F.data == "AdBuyMenu|menu")
    router.callback_query.register(show_creatives, F.data == "AdBuyMenu|creatives")
    router.callback_query.register(show_purchases, F.data == "AdBuyMenu|purchases")
    router.callback_query.register(back_to_main, F.data == "AdBuyMenu|back")
    return router
