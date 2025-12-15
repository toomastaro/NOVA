from aiogram import Router, F, types
from main_bot.keyboards import InlineAdCreative
from main_bot.utils.lang.language import text
from main_bot.utils.error_handler import safe_handler

router = Router(name="AdCreativeMenu")

@router.message(F.text == "Рекламные креативы")
@safe_handler("Show Ad Creative Menu")
async def show_ad_creative_menu(message: types.Message):
    """Показывает главное меню рекламных креативов."""
    await message.answer(
        text('ad_creative:menu_title'),
        reply_markup=InlineAdCreative.menu()
    )
