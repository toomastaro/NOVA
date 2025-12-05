from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from main_bot.database.db import db
from main_bot.keyboards import InlineAdPurchase

router = Router(name="AdPurchaseMenu")

@router.message(F.text == "Рекламные закупы")
async def show_ad_purchase_menu(message: types.Message):
    await message.answer("Рекламные закупы:", reply_markup=InlineAdPurchase.main_menu())


@router.callback_query(F.data == "AdPurchase|menu")
async def show_ad_purchase_menu_callback(call: CallbackQuery):
    await call.message.edit_text("Рекламные закупы:", reply_markup=InlineAdPurchase.main_menu())


@router.callback_query(F.data == "AdPurchase|create_menu")
async def show_creative_selection(call: CallbackQuery):
    creatives = await db.get_user_creatives(call.from_user.id)
    if not creatives:
        await call.answer("У вас нет креативов. Сначала создайте креатив.", show_alert=True)
        return
        
    await call.message.edit_text(
        "Выберите креатив для создания закупа:", 
        reply_markup=InlineAdPurchase.creative_selection_menu(creatives)
    )


@router.callback_query(F.data == "AdPurchase|list")
async def show_purchase_list(call: CallbackQuery):
    purchases = await db.get_user_purchases(call.from_user.id)
    if not purchases:
        await call.answer("У вас пока нет закупов.", show_alert=True)
        return
    
    # Enrich purchases with creative names
    # This is N+1 but acceptable for small lists. Ideally join in DB.
    # For now, let's fetch creative for each purchase
    enriched_purchases = []
    for p in purchases:
        creative = await db.get_creative(p.creative_id)
        p.creative_name = creative.name if creative else "Unknown"
        enriched_purchases.append(p)
        
    await call.message.edit_text(
        "Ваши закупы:", 
        reply_markup=InlineAdPurchase.purchase_list_menu(enriched_purchases)
    )

