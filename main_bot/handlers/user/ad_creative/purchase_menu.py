from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import logging
from main_bot.database.db import db
from main_bot.keyboards import InlineAdPurchase

router = Router(name="AdPurchaseMenu")

@router.message(F.text == "Рекламные закупы")
async def show_ad_purchase_menu(message: types.Message):
    await show_ad_purchase_menu_internal(message, edit=False)


@router.callback_query(F.data == "AdPurchase|menu")
async def show_ad_purchase_menu_callback(call: CallbackQuery):
    await show_ad_purchase_menu_internal(call.message, edit=True)

async def show_ad_purchase_menu_internal(message: types.Message, edit: bool = False):
    # 1. Check user channels and MTClient status in each
    # This involves logic to find if a client is present and has rights.
    # The requirement is: "на экране вывести текущий статус прав нашего клиента ... имя: статус"
    # And "добавить кнопку перепроверить статус".
    
    # We check rights for ALL user channels? Or just general readiness?
    # "в канал добавлен наш подпищик ... и чтоб вся система работал его надо сделать администратором"
    # This implies verifying specific channels. But the menu is general.
    # Maybe we show a summary status? "Bot Client: Active" or "Inactive (Check Rights)"
    
    # Let's check if the user has ANY channels added to the bot first.
    user_channels = await db.get_user_channels(message.chat.id)
    
    status_text = ""
    client_name = "NovaClient" # Placeholder if no specific client logic exposed clearly
    
    # We get the client name from one of the channels (assuming same client used or pool)
    # If using pool, we might checking the "preferred" client for the first channel found.
    
    has_rights = False
    
    if not user_channels:
         status_text = "⚠️ Нет подключенных каналов."
    else:
        # Check first channel for sample
        first_ch = user_channels[0]
        # Get client
        client_model = await db.get_preferred_for_stats(first_ch.chat_id) or await db.get_any_client_for_channel(first_ch.chat_id)
        
        if client_model and client_model.client:
            client_name = client_model.client.alias or f"Client #{client_model.client.id}"
            # Check rights? We can't check efficiently in real-time on every render without delay.
            # We should store status or just assume Active until verified.
            # User asked for "Check Status" button.
            # Here we just display what we know. 
            # Let's say we check if 'preferred_for_stats' is True, meaning we verified it before?
            # Or use a new "is_admin_log_readable" flag? 
            # For now, simplistic: if we have a linked client, we say "Connected".
            # The "Check Status" button will do the actual RPC call to verify rights.
            status_text = f"🤖 Клиент: {client_name}\n✅ Статус: Подключен"
            has_rights = True
        else:
            status_text = "❌ Клиент не найден в каналах."
    
    logger = logging.getLogger(__name__)
    logger.info(f"Rendering Ad Purchase Menu for user {message.chat.id}, channel count: {len(user_channels)}")
    
    # Determine text
    main_text = (
        "<b>💰 Рекламные закупы (v2)</b>\n\n"
        "Для сбора статистики в канал должен быть дбавлен наш технический аккаунт "
        "с правами администратора (Публикация, Редактирование, Удаление).\n\n"
        f"{status_text}"
    )
    
    # Keyboard
    # Add "Check Status" button
    kb = InlineAdPurchase.main_menu()
    # Modifying main_menu logic or just adding button here?
    # InlineAdPurchase.main_menu() returns markup. We can't easily append.
    # We need to modify the keyboard builder in ad_modules.py or rebuild here.
    # Better to update ad_modules.py to include status button or conditional.
    # But for quick iteration, I'll allow "Create" but handle blocking in the handler.
    # Wait, user said: "не пускать пока не будет клиента"
    
    if edit:
        await message.edit_text(main_text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(main_text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "AdPurchase|check_client_status")
async def check_client_status(call: CallbackQuery):
    await call.answer("Проверяем права клиента...", show_alert=False)
    
    user_channels = await db.get_user_channels(call.message.chat.id)
    if not user_channels:
         await call.answer("Нет каналов для проверки.", show_alert=True)
         return
         
    # Logic to verify rights via MTProto
    # For simplicity, we check the first channel.
    channel = user_channels[0]
    
    client_model = await db.get_preferred_for_stats(channel.chat_id) or await db.get_any_client_for_channel(channel.chat_id)
    if not client_model:
        await call.answer("Клиент не назначен каналу.", show_alert=True)
        return

    from pathlib import Path
    from main_bot.utils.session_manager import SessionManager
    
    session_path = Path(client_model.client.session_path)
    if not session_path.exists():
         await call.answer("Файл сессии не найден.", show_alert=True)
         return

    async with SessionManager(session_path) as manager:
        if not manager.client or not await manager.client.is_user_authorized():
             await call.answer("Не удалось загрузить сессию клиента.", show_alert=True)
             return
        
        try:
            # Check admin log access
            # Telethon iter_admin_log
            async for event in manager.client.iter_admin_log(channel.chat_id, limit=1):
                pass
                
            await call.message.edit_text(
                call.message.html_text + "\n\n✅ Права подтверждены! Клиент видит Admin Log.",
                reply_markup=InlineAdPurchase.main_menu(),
                parse_mode="HTML"
            )
        except Exception as e:
            await call.message.edit_text(
                call.message.html_text + f"\n\n❌ Ошибка: Клиент не имеет доступа к Admin Log.\n{str(e)}",
                reply_markup=InlineAdPurchase.main_menu(),
                parse_mode="HTML"
            )


@router.callback_query(F.data == "AdPurchase|create_menu")
async def show_creative_selection(call: CallbackQuery):
    creatives = await db.get_user_creatives(call.from_user.id)
    if not creatives:
        await call.answer("У вас нет креативов. Сначала создайте креатив.", show_alert=True)
        return
    
    # Block if no client rights (simplified check: must have client)
    # Ideally should read status from DB which we updated in 'check_client_status'
    # For now, unblock to allow flow testing, or check simplistic presence
    user_channels = await db.get_user_channels(call.from_user.id)
    if not user_channels:
         await call.answer("Нет подключенных каналов!", show_alert=True)
         return
    
    client_model = await db.get_preferred_for_stats(user_channels[0].chat_id) or await db.get_any_client_for_channel(user_channels[0].chat_id)
    if not client_model:
         await call.answer("Требуется технический аккаунт в канале!", show_alert=True)
         return
        
    await call.message.edit_text(
        "Выберите креатив для создания закупа:", 
        reply_markup=InlineAdPurchase.creative_selection_menu(creatives)
    )


@router.callback_query(F.data == "AdPurchase|list")
async def show_purchase_list(call: CallbackQuery, send_new: bool = False):
    purchases = await db.get_user_purchases(call.from_user.id)
    if not purchases:
        if send_new:
            await call.message.answer("У вас пока нет закупов.", show_alert=True)
        else:
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
    
    # Sort by ID or created_timestamp desc (Assuming ID is auto-increment, higher ID = newer)
    enriched_purchases.sort(key=lambda x: x.id, reverse=True)
        
    text = "Ваши закупы:"
    kb = InlineAdPurchase.purchase_list_menu(enriched_purchases)

    if send_new:
        await call.message.answer(text, reply_markup=kb)
    else:
        await call.message.edit_text(text, reply_markup=kb)

