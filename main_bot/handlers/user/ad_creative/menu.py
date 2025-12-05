from aiogram import Router, F, types
from main_bot.keyboards import InlineAdCreative

router = Router(name="AdCreativeMenu")

@router.message(F.text == "Рекламные креативы")
async def show_ad_creative_menu(message: types.Message):
    await message.answer("Рекламные креативы", reply_markup=InlineAdCreative.menu())
