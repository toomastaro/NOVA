from aiogram import Router, F, types
from main_bot.database.db import db
from main_bot.keyboards.keyboards import InlineAdPurchase

router = Router(name="AdPurchaseMenu")

@router.message(F.text == "Мои закупы")
async def show_ad_purchase_menu(message: types.Message):
    # For now, just show a list of purchases or a placeholder
    # The prompt said: "В списке закупов (новый раздел "Мои закупы") сделай: вывод всех AdPurchase пользователя"
    
    purchases = await db.get_user_purchases(message.from_user.id)
    if not purchases:
        await message.answer("У вас пока нет закупов.")
        return
        
    # We need a list UI for purchases.
    # I'll add a simple inline list here or reuse a builder if I had one.
    # I didn't create a specific PurchaseList builder in keyboards.py yet.
    # I will create a simple inline keyboard here dynamically or add to keyboards.py
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    for p in purchases:
        kb.button(
            text=f"#{p.id} {p.pricing_type} {p.price_value}р.",
            callback_data=f"AdPurchase|mapping|{p.id}" # Direct link to mapping as requested
        )
    kb.adjust(1)
    
    await message.answer("Ваши закупы:", reply_markup=kb.as_markup())
