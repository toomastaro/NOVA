from aiogram import Router, F, types
from main_bot.keyboards import InlineAdCreative, InlineAdPurchase

router = Router(name="AdBuyMenu")

@router.message(F.text == "🛒 Закуп")
async def show_ad_buy_menu(message: types.Message):
    """Показать меню закупов с рекламными креативами и закупами"""
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🎨 Рекламные креативы", callback_data="AdBuyMenu|creatives")],
        [types.InlineKeyboardButton(text="💰 Рекламные закупы", callback_data="AdBuyMenu|purchases")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="AdBuyMenu|back")]
    ])
    await message.answer("🛒 <b>Закуп</b>\n\nВыберите раздел:", reply_markup=kb)


@router.callback_query(F.data == "AdBuyMenu|creatives")
async def show_creatives(call: types.CallbackQuery):
    """Показать меню рекламных креативов"""
    await call.message.edit_text("🎨 Рекламные креативы", reply_markup=InlineAdCreative.menu())


@router.callback_query(F.data == "AdBuyMenu|purchases")
async def show_purchases(call: types.CallbackQuery):
    """Показать меню рекламных закупов"""
    await call.message.edit_text("💰 Рекламные закупы", reply_markup=InlineAdPurchase.menu())


@router.callback_query(F.data == "AdBuyMenu|back")
async def back_to_main(call: types.CallbackQuery):
    """Возврат в главное меню"""
    from main_bot.keyboards.common import Reply
    await call.message.delete()
    await call.message.answer(
        "Главное меню",
        reply_markup=Reply.menu()
    )
