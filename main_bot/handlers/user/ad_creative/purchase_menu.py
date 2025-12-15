"""
Модуль меню закупов рекламы.
Отображает списки закупов, проверяет статус технического аккаунта.
"""
import logging
from pathlib import Path

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from main_bot.database.db import db
from main_bot.keyboards import InlineAdPurchase
from main_bot.utils.error_handler import safe_handler
from main_bot.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)

router = Router(name="AdPurchaseMenu")

@router.message(F.text == "Рекламные закупы")
@safe_handler("Show Ad Purchase Menu")
async def show_ad_purchase_menu(message: types.Message):
    """Показ меню закупов (сообщение)."""
    await show_ad_purchase_menu_internal(message, edit=False)


@router.callback_query(F.data == "AdPurchase|menu")
@safe_handler("Show Ad Purchase Menu Callback")
async def show_ad_purchase_menu_callback(call: CallbackQuery):
    """Показ меню закупов (callback)."""
    await show_ad_purchase_menu_internal(call.message, edit=True)

@safe_handler("Show Ad Purchase Menu Internal")
async def show_ad_purchase_menu_internal(message: types.Message, edit: bool = False):
    """Внутренняя функция отображения меню закупов."""
.
    user_channels = await db.channel.get_user_channels(message.chat.id)
    
    status_text = ""
    client_name = "NovaClient" # Placeholder if no specific client logic exposed clearly
    

    
    has_rights = False
    
    if not user_channels:
         status_text = "⚠️ Нет подключенных каналов."
    else:
        # Check first channel for sample
        first_ch = user_channels[0]
        # Get client
        client_model = await db.mt_client_channel.get_preferred_for_stats(first_ch.chat_id) or await db.mt_client_channel.get_any_client_for_channel(first_ch.chat_id)
        
        if client_model and client_model.client:
            client_name = client_model.client.alias or f"Client #{client_model.client.id}"

            status_text = f"🤖 Клиент: {client_name}\n✅ Статус: Подключен"
            has_rights = True
        else:
            status_text = "❌ Клиент не найден в каналах."
    
    logger.info(f"Rendering Ad Purchase Menu for user {message.chat.id}, channel count: {len(user_channels)}")
    
    # Determine text
    main_text = (
        "<b>💰 Рекламные закупы</b>\n\n"
        "Для сбора статистики в канал должен быть добавлен наш технический аккаунт "
        "с правами администратора (Публикация, Редактирование, Удаление).\n\n"
        f"{status_text}"
    )
    
    # Keyboard
    # Add "Check Status" button
    kb = InlineAdPurchase.main_menu()
    
    if edit:
        await message.edit_text(main_text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(main_text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "AdPurchase|check_client_status")
@safe_handler("Check Client Status")
async def check_client_status(call: CallbackQuery):
    """Проверка статуса подключения технических аккаунтов."""
    await call.answer("⏳ Полная проверка всех каналов...", show_alert=False)
    
    user_channels = await db.channel.get_user_channels(call.message.chat.id)
    if not user_channels:
         await call.answer("Нет каналов для проверки.", show_alert=True)
         return
         
    # Group channels by client to optimize sessions
    client_groups = {} # {client_id: {'client': mt_client, 'channels': [channel]}}
    no_client_channels = []
    
    for channel in user_channels:
        client_model = await db.mt_client_channel.get_preferred_for_stats(channel.chat_id) or await db.mt_client_channel.get_any_client_for_channel(channel.chat_id)
        
        if not client_model or not client_model.client:
            no_client_channels.append(channel)
            continue
            
        mt_client = client_model.client
        if mt_client.id not in client_groups:
            client_groups[mt_client.id] = {
                'client': mt_client,
                'channels': []
            }
        client_groups[mt_client.id]['channels'].append(channel)
        
    results = []
    
    # 1. Channels with no client
    for ch in no_client_channels:
        results.append(f"❌ <b>{ch.title}</b>: Не назначен помощник")
        
    # 2. Check each client group
    # from pathlib import Path
    # from main_bot.utils.session_manager import SessionManager
    
    for cid, group in client_groups.items():
        mt_client = group['client']
        channels = group['channels']
        session_path = Path(mt_client.session_path)
        client_label = mt_client.alias or f"Client {cid}"
        
        if not session_path.exists():
            for ch in channels:
                results.append(f"❌ <b>{ch.title}</b>: Нет файла сессии ({client_label})")
            continue
            
        try:
            async with SessionManager(session_path) as manager:
                if not manager.client or not await manager.client.is_user_authorized():
                    for ch in channels:
                        results.append(f"❌ <b>{ch.title}</b>: Сессия не авторизована ({client_label})")
                    continue
                
                # Check permissions for each channel
                for ch in channels:
                    try:
                        # Attempt to read admin log to verify admin rights
                        async for event in manager.client.iter_admin_log(ch.chat_id, limit=1):
                            pass
                        results.append(f"✅ <b>{ch.title}</b>")
                    except Exception as e:
                        err_str = str(e)
                        if "ChatAdminRequiredError" in err_str:
                             error_msg = "Нет прав админа"
                        else:
                             error_msg = "Ошибка доступа"
                        results.append(f"❌ <b>{ch.title}</b>: {error_msg}")
                        logger.error(f"Check failed for {ch.title}: {e}")
                        
        except Exception as e:
            logger.error(f"Session error for {client_label}: {e}")
            for ch in channels:
                results.append(f"❌ <b>{ch.title}</b>: Ошибка подключения ({client_label})")

    # Build Report
    success_count = sum(1 for r in results if r.startswith("✅"))
    total_count = len(user_channels)
    
    report_header = f"📊 <b>Результат проверки ({success_count}/{total_count})</b>"
    if len(results) > 20: 
        # Shorten if too many?
        # User asked for status, so full list is expected but maybe split messages if > 4096 chars.
        # Generally 20 lines is fine.
        pass
        
    report_body = "\n".join(results)
    
    main_text = (
        "<b>💰 Рекламные закупы</b>\n\n"
        "Для сбора статистики в канал должен быть добавлен наш технический аккаунт "
        "с правами администратора.\n\n"
        f"{report_header}\n"
        f"{report_body}"
    )
    
    await call.message.edit_text(
        text=main_text,
        reply_markup=InlineAdPurchase.main_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "AdPurchase|create_menu")
@safe_handler("Show Creative Selection")
async def show_creative_selection(call: CallbackQuery):
    """Меню выбора креатива для создания закупа."""
    creatives = await db.ad_creative.get_user_creatives(call.from_user.id)
    if not creatives:
        await call.answer("У вас нет креативов. Сначала создайте креатив.", show_alert=True)
        return
    
    # Block if no client rights (simplified check: must have client)
    # Ideally should read status from DB which we updated in 'check_client_status'
    # For now, unblock to allow flow testing, or check simplistic presence
    user_channels = await db.channel.get_user_channels(call.from_user.id)
    if not user_channels:
         await call.answer("Нет подключенных каналов!", show_alert=True)
         return
    
    client_model = await db.mt_client_channel.get_preferred_for_stats(user_channels[0].chat_id) or await db.mt_client_channel.get_any_client_for_channel(user_channels[0].chat_id)
    if not client_model:
         await call.answer("Требуется технический аккаунт в канале!", show_alert=True)
         return
        
    await call.message.edit_text(
        "Выберите креатив для создания закупа:", 
        reply_markup=InlineAdPurchase.creative_selection_menu(creatives)
    )


@router.callback_query(F.data == "AdPurchase|list")
@safe_handler("Show Purchase List")
async def show_purchase_list(call: CallbackQuery, send_new: bool = False):
    """Список закупов пользователя."""
    purchases = await db.ad_purchase.get_user_purchases(call.from_user.id)
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
        creative = await db.ad_creative.get_creative(p.creative_id)
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

