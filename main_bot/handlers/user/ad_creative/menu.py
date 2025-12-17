"""
Модуль меню рекламных креативов.

Обрабатывает входную точку в меню управления креативами.
"""

from aiogram import Router, F, types
from main_bot.keyboards import InlineAdCreative
from main_bot.utils.lang.language import text
from utils.error_handler import safe_handler

router = Router(name="AdCreativeMenu")


@router.message(F.text == "Рекламные креативы")
@safe_handler("Show Ad Creative Menu")
async def show_ad_creative_menu(message: types.Message) -> None:
    """
    Показывает главное меню рекламных креативов.

    Аргументы:
        message (types.Message): Сообщение пользователя.
    """
    await message.answer(
        text("ad_creative:menu_title"), reply_markup=InlineAdCreative.menu()
    )
