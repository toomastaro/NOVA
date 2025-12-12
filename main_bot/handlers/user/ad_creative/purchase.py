import re
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from main_bot.database.db import db
from main_bot.database.types import AdPricingType, AdTargetType
from main_bot.database.ad_purchase.model import AdPurchase
from main_bot.keyboards import keyboards, InlineAdPurchase, InlineAdCreative
from main_bot.states.user import AdPurchaseStates
from main_bot.utils.lang.language import text


router = Router(name="AdPurchase")


@router.callback_query(F.data.startswith("AdPurchase|create|"))
async def create_purchase_start(call: CallbackQuery, state: FSMContext):
    creative_id = int(call.data.split("|")[2])
    await state.update_data(creative_id=creative_id)
    
    await call.message.edit_text(
        "Выберите тип оплаты:",
        reply_markup=InlineAdPurchase.pricing_type_menu()
    )
    await state.set_state(AdPurchaseStates.waiting_for_pricing_type)


@router.callback_query(F.data.startswith("AdPurchase|pricing|"))
async def process_pricing_type(call: CallbackQuery, state: FSMContext):
    pricing_type_str = call.data.split("|")[2]
    # Validate enum
    try:
        pricing_type = AdPricingType(pricing_type_str)
    except ValueError:
        await call.answer("Ошибка типа оплаты")
        return

    await state.update_data(pricing_type=pricing_type)
    
    await call.message.edit_text(
        "Введите ставку (целое число, рубли):",
        reply_markup=None
    )
    await state.set_state(AdPurchaseStates.waiting_for_price)


@router.message(AdPurchaseStates.waiting_for_price)
async def process_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.strip())
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректное целое число.")
        return

    await state.update_data(price_value=price)
    await message.answer("Введите комментарий к закупу (условия, канал и т.д.):")
    await state.set_state(AdPurchaseStates.waiting_for_comment)


@router.message(AdPurchaseStates.waiting_for_comment)
async def process_comment(message: Message, state: FSMContext):
    comment = message.text.strip()
    data = await state.get_data()
    
    # Create Purchase
    purchase_id = await db.create_purchase(
        owner_id=message.from_user.id,
        creative_id=data['creative_id'],
        pricing_type=data['pricing_type'],
        price_value=data['price_value'],
        comment=comment
    )
    
    await message.answer(f"Закуп #{purchase_id} создан! Переходим к мапингу ссылок...")
    
    # Start Mapping Logic
    await start_mapping(message, purchase_id, data['creative_id'])
    await state.clear()


async def start_mapping(message: Message, purchase_id: int, creative_id: int):
    slots = await db.get_slots(creative_id)
    user_channels = await db.get_user_channels(message.chat.id)
    
    # Auto-detection
    for slot in slots:
        # Check if mapping already exists
        # We don't have a direct get_mapping(purchase_id, slot_id) but upsert handles it.
        # But we want to preserve existing mappings if we re-enter this flow?
        # The prompt says: "если уже есть AdPurchaseLinkMapping ... используй его"
        # Since upsert updates if exists, we should check first or just rely on upsert logic if we want to overwrite?
        # Actually, if we re-enter mapping, we shouldn't overwrite manual changes.
        # So we should check if mapping exists.
        
        # Since we don't have a specific check method exposed in crud easily without fetching all, 
        # let's fetch all mappings for this purchase first.
        existing_mappings = await db.get_link_mappings(purchase_id)
        existing_slot_ids = [m.slot_id for m in existing_mappings]
        
        if slot.id in existing_slot_ids:
            continue

        target_type = AdTargetType.EXTERNAL
        target_channel_id = None
        track_enabled = False
        
        url = slot.original_url.lower()
        
        # 1. Check t.me/username
        # Simplified check: if any user channel has this username in link?
        # We don't have usernames in Channel model. 
        # So we default to EXTERNAL as per previous iteration decision.
        
        # 2. Check invite link
        # Default to EXTERNAL.
        
        # If user channel is found (hypothetically):
        # target_type = AdTargetType.CHANNEL
        # target_channel_id = channel.chat_id
        # track_enabled = True
        
        await db.upsert_link_mapping(
            ad_purchase_id=purchase_id,
            slot_id=slot.id,
            original_url=slot.original_url,
            target_type=target_type,
            target_channel_id=target_channel_id,
            track_enabled=track_enabled
        )

    await show_mapping_menu(message, purchase_id)


async def show_mapping_menu(message: Message, purchase_id: int):
    mappings = await db.get_link_mappings(purchase_id)
    user_channels = await db.get_user_channels(message.chat.id)
    channels_map = {ch.chat_id: ch.title for ch in user_channels}
    
    links_data = []
    for m in mappings:
        status_text = "❌ Без трекинга"
        if m.target_type == AdTargetType.CHANNEL and m.target_channel_id:
            status_text = channels_map.get(m.target_channel_id, "Неизвестный канал")
        elif m.target_type == AdTargetType.EXTERNAL:
            status_text = "❌ Без трекинга"
            
        links_data.append({
            "slot_id": m.slot_id,
            "original_url": m.original_url[:30] + "..." if len(m.original_url) > 30 else m.original_url,
            "status_text": status_text
        })
        
    await message.answer(
        f"В креативе найдено {len(mappings)} ссылок. Привяжите каждую ссылку к каналу или отключите трекинг.",
        reply_markup=InlineAdPurchase.mapping_menu(purchase_id, links_data),
        disable_web_page_preview=True
    )


@router.callback_query(F.data.startswith("AdPurchase|map_link|"))
async def edit_link_mapping(call: CallbackQuery):
    _, _, purchase_id, slot_id = call.data.split("|")
    purchase_id = int(purchase_id)
    slot_id = int(slot_id)
    
    await call.message.edit_text(
        "Выберите действие для этой ссылки:",
        reply_markup=InlineAdPurchase.link_actions_menu(purchase_id, slot_id)
    )


@router.callback_query(F.data.startswith("AdPurchase|select_channel_list|"))
async def show_channel_list(call: CallbackQuery):
    _, _, purchase_id, slot_id = call.data.split("|")
    purchase_id = int(purchase_id)
    slot_id = int(slot_id)
    
    channels = await db.get_user_channels(call.from_user.id)
    
    await call.message.edit_text(
        "Выберите канал:",
        reply_markup=InlineAdPurchase.channel_list_menu(purchase_id, slot_id, channels)
    )


@router.callback_query(F.data.startswith("AdPurchase|set_channel|"))
async def save_mapping_channel(call: CallbackQuery):
    _, _, purchase_id, slot_id, channel_id = call.data.split("|")
    purchase_id = int(purchase_id)
    slot_id = int(slot_id)
    channel_id = int(channel_id)
    
    # Check subscription
    channel = await db.get_channel_by_chat_id(channel_id)
    if not channel:
        await call.answer("Канал не найден", show_alert=True)
        return
        
    import time
    if not channel.subscribe or channel.subscribe < time.time():
        await call.answer("У канала нет активной подписки. Продлите подписку для использования.", show_alert=True)
        return
    
    await db.upsert_link_mapping(
        ad_purchase_id=purchase_id,
        slot_id=slot_id,
        target_type=AdTargetType.CHANNEL,
        target_channel_id=channel_id,
        track_enabled=True
    )
    
    # Refresh menu
    await call.message.delete()
    await show_mapping_menu(call.message, purchase_id)


@router.callback_query(F.data.startswith("AdPurchase|set_external|"))
async def save_mapping_external(call: CallbackQuery):
    _, _, purchase_id, slot_id = call.data.split("|")
    purchase_id = int(purchase_id)
    slot_id = int(slot_id)
    
    await db.upsert_link_mapping(
        ad_purchase_id=purchase_id,
        slot_id=slot_id,
        target_type=AdTargetType.EXTERNAL,
        target_channel_id=None,
        track_enabled=False
    )
    
    # Refresh menu
    await call.message.delete()
    await show_mapping_menu(call.message, purchase_id)


@router.callback_query(F.data.startswith("AdPurchase|mapping|"))
async def back_to_mapping(call: CallbackQuery):
    purchase_id = int(call.data.split("|")[2])
    await call.message.delete()
    await show_mapping_menu(call.message, purchase_id)


@router.callback_query(F.data.startswith("AdPurchase|save_mapping|"))
async def finish_mapping(call: CallbackQuery):
    purchase_id = int(call.data.split("|")[2])
    await call.answer("Мапинг сохранен")
    # Return to purchase view
    await view_purchase(call, purchase_id)


@router.callback_query(F.data == "AdPurchase|cancel")
async def cancel_purchase(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer("Создание закупа отменено.")


@router.callback_query(F.data.startswith("AdPurchase|view|"))
async def view_purchase_callback(call: CallbackQuery):
    purchase_id = int(call.data.split("|")[2])
    await view_purchase(call, purchase_id)


async def view_purchase(call: CallbackQuery, purchase_id: int):
    purchase = await db.get_purchase(purchase_id)
    if not purchase:
        await call.answer("Закуп не найден", show_alert=True)
        return

    creative = await db.get_creative(purchase.creative_id)
    creative_name = creative.name if creative else "Unknown"
    
    # Localize status
    status_map = {
        "active": "🟢 Активен",
        "paused": "⏸ На паузе",
        "deleted": "🗑 Удален",
        "completed": "🏁 Завершен"
    }
    status_text = status_map.get(purchase.status, purchase.status)
    
    text = (
        f"💳 <b>Закуп: «{purchase.comment or 'Нет названия'}»</b>\n"
        f"🎨 Креатив: {creative_name}\n"
        f"📊 Тип: {purchase.pricing_type.value}\n"
        f"💸 Ставка: {purchase.price_value} руб.\n"
        f"📋 Комментарий: {purchase.comment or 'Нет'}\n"
        f"📌 Статус: {status_text}"
    )
    
    # If message is not modified, edit_text might fail, so we try/except or just ignore
    try:
        await call.message.edit_text(
            text,
            reply_markup=InlineAdPurchase.purchase_view_menu(purchase.id),
            parse_mode="HTML"
        )
    except Exception:
        await call.message.answer(
            text,
            reply_markup=InlineAdPurchase.purchase_view_menu(purchase.id),
            parse_mode="HTML"
        )





@router.callback_query(F.data.startswith("AdPurchase|delete|"))
async def delete_purchase(call: CallbackQuery):
    purchase_id = int(call.data.split("|")[2])
    await db.update_purchase_status(purchase_id, "deleted")
    await call.answer("Закуп удален")
    
    # Check remaining
    purchases = await db.get_user_purchases(call.from_user.id)
    # Filter out deleted if get_user_purchases returns deleted ones? 
    # CRUD get_user_purchases filters status != 'deleted'.
    
    if not purchases:
        # No purchases left, go to main Purchases menu
        # AdPurchase|menu handler edits text to "Purchases menu"
        # We can simulate it or send message
        await call.message.edit_text("💰 Рекламные закупы", reply_markup=InlineAdPurchase.main_menu())
    else:
        from main_bot.handlers.user.ad_creative.purchase_menu import show_purchase_list
        await show_purchase_list(call)


@router.callback_query(F.data.startswith("AdPurchase|stats|"))
async def show_stats_default(call: CallbackQuery):
    # Default to 24h view
    purchase_id = int(call.data.split("|")[2])
    await render_purchase_stats(call, purchase_id, "24h")


@router.callback_query(F.data.startswith("AdPurchase|stats_period|"))
async def show_stats_period(call: CallbackQuery):
    parts = call.data.split("|")
    purchase_id = int(parts[2])
    period = parts[3]
    await render_purchase_stats(call, purchase_id, period)


async def render_purchase_stats(call: CallbackQuery, purchase_id: int, period: str):
    # Calculate time range
    import time
    now = int(time.time())
    
    if period == "24h":
        from_ts = now - (24 * 3600)
        period_name = "24 часа"
    elif period == "7d":
        from_ts = now - (7 * 24 * 3600)
        period_name = "7 дней"
    elif period == "30d":
        from_ts = now - (30 * 24 * 3600)
        period_name = "30 дней"
    else:  # all
        from_ts = None
        period_name = "всё время"
    
    to_ts = now
    
    # Get purchase info
    purchase = await db.get_purchase(purchase_id)
    if not purchase:
        await call.answer("Закуп не найден", show_alert=True)
        return
    
    # Get statistics
    leads_count = await db.get_leads_count(purchase_id)
    subs_count = await db.get_subscriptions_count(purchase_id, from_ts, to_ts)
    
    # Get per-channel statistics
    mappings = await db.get_link_mappings(purchase_id)
    channels_stats = {}
    total_unsubs = 0  # Общее количество отписок
    
    for m in mappings:
        if m.target_channel_id:
            # Setup calc
            if m.target_channel_id not in channels_stats:
                channel = await db.get_channel_by_chat_id(m.target_channel_id)
                channels_stats[m.target_channel_id] = {
                    "name": channel.title if channel else f"ID: {m.target_channel_id}",
                    "leads": 0,
                    "subs": 0,
                    "unsubs": 0
                }
            
            # Leads (linked to slot)
            slot_leads = await db.get_leads_by_slot(purchase_id, m.slot_id)
            channels_stats[m.target_channel_id]["leads"] += len(slot_leads)
            
            # Subs (linked to slot/channel)
            slot_subs_all = await db.get_subscriptions_by_slot(purchase_id, m.slot_id, from_ts, to_ts)
            
            # Filter
            active_subs = [s for s in slot_subs_all if s.status == 'active']
            left_subs = [s for s in slot_subs_all if s.status != 'active']
            
            channels_stats[m.target_channel_id]["subs"] += len(active_subs)
            channels_stats[m.target_channel_id]["unsubs"] += len(left_subs)
            total_unsubs += len(left_subs)

    # Формируем статистику в зависимости от типа оплаты
    pricing_type = purchase.pricing_type.value
    
    if pricing_type == "FIXED":
        # Фиксированная оплата
        # Расчет цены за заявку и подписку
        cost_per_lead = (purchase.price_value / leads_count) if leads_count > 0 else 0
        cost_per_sub = (purchase.price_value / subs_count) if subs_count > 0 else 0
        
        stats_text = (
            f"📊 <b>Статистика закупа: «{purchase.comment or 'Нет названия'}»</b>\n"
            f"Период: {period_name}\n\n"
            f"📎 Заявок: {leads_count}\n"
            f"👥 Присоединились: {subs_count}\n"
            f"� Отписалось: {total_unsubs}\n"
            f"💵 Цена заявки/подписки: {cost_per_lead:.2f}₽ / {cost_per_sub:.2f}₽\n"
            f"💳 Тип оплаты: Фиксированная\n"
            f"💰 Цена: {purchase.price_value} руб."
        )
        
    elif pricing_type == "CPL":
        # Оплата за заявку
        total_cost = leads_count * purchase.price_value
        
        stats_text = (
            f"📊 <b>Статистика закупа: «{purchase.comment or 'Нет названия'}»</b>\n"
            f"Период: {period_name}\n\n"
            f"📎 Заявок: {leads_count}\n"
            f"👥 Присоединились: {subs_count}\n"
            f"📉 Отписалось: {total_unsubs}\n"
            f"💵 Цена заявки: {purchase.price_value}₽\n"
            f"💳 Тип оплаты: По заявкам\n"
            f"💰 Цена: {total_cost} руб."
        )
        
    elif pricing_type == "CPS":
        # Оплата за подписку
        total_cost = subs_count * purchase.price_value
        
        stats_text = (
            f"📊 <b>Статистика закупа: «{purchase.comment or 'Нет названия'}»</b>\n"
            f"Период: {period_name}\n\n"
            f"📎 Заявок: {leads_count}\n"
            f"👥 Присоединились: {subs_count}\n"
            f"📉 Отписалось: {total_unsubs}\n"
            f"💵 Цена подписки: {purchase.price_value}₽\n"
            f"💳 Тип оплаты: По подпискам\n"
            f"💰 Цена: {total_cost} руб."
        )
    else:
        # Fallback для неизвестного типа
        stats_text = (
            f"📊 <b>Статистика закупа: «{purchase.comment or 'Нет названия'}»</b>\n"
            f"Период: {period_name}\n\n"
            f"📎 Заявок: {leads_count}\n"
            f"👥 Подписок: {subs_count}\n"
            f"💵 Тип оплаты: {pricing_type}\n"
            f"💸 Ставка: {purchase.price_value} руб."
        )
    
    # Add per-channel breakdown
    if channels_stats:
        stats_text += "\n\n<b>📺 По каналам:</b>\n"
        for ch_id, ch_data in channels_stats.items():
            stats_text += (
                f"• {ch_data['name']}:\n"
                f"{ch_data['leads']} заявок | {ch_data['subs']} подписок | {ch_data['unsubs']} отписок\n"
            )
            
    # Try/except for edit_text to avoid "message not modified" error if user clicks same period
    try:
        await call.message.edit_text(
            stats_text,
            reply_markup=InlineAdPurchase.stats_period_menu(purchase_id),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception:
        await call.answer()


@router.callback_query(F.data == "AdPurchase|global_stats")
async def show_global_stats_menu(call: CallbackQuery):
    # Show user's global statistics
    
    await call.message.edit_text(
        "Выберите период создания закупов для получения Excel-отчета по всем закупам.",
        reply_markup=InlineAdPurchase.global_stats_period_menu()
    )


@router.callback_query(F.data.startswith("AdPurchase|global_stats_period|"))
async def show_global_stats(call: CallbackQuery):
    # Export Excel report
    
    period = call.data.split("|")[2]
    
    # Calculate time range for CREATION DATE
    import time
    from datetime import datetime
    now = int(time.time())
    
    if period == "24h":
        from_ts = now - (24 * 3600)
        period_name = "24_hours"
    elif period == "7d":
        from_ts = now - (7 * 24 * 3600)
        period_name = "7_days"
    elif period == "30d":
        from_ts = now - (30 * 24 * 3600)
        period_name = "30_days"
    else:  # all
        from_ts = 0
        period_name = "all_time"
    
    to_ts = now
    
    user_id = call.from_user.id
    
    # 1. Fetch purchases created in this range
    # Ensure db method supports filtering by created_timestamp. 
    # get_user_purchases doesn't have args in current crud, but get_user_global_stats uses filter logic.
    # We need a new query or use existing one filtered.
    # I'll fetch all and filter in python for now to avoid modifying CRUD if not strictly needed, 
    # but `get_user_purchases` is by owner_id.
    all_purchases = await db.get_user_purchases(user_id)
    purchases = [p for p in all_purchases if p.created_timestamp >= from_ts and p.created_timestamp <= to_ts]
    
    if not purchases:
        await call.answer("За этот период закупов не найдено.", show_alert=True)
        return
    
    await call.answer("Генерация отчета...")
    
    # 2. Build Excel
    import openpyxl
    from openpyxl import Workbook
    from io import BytesIO
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Statistics"
    
    # Headers
    # дата:название_креатива:комментарий:фикс_цена:цена заявки:зена подпищика:заявок подано:подписок:цена за подпищика:цена за заявку
    headers = [
        "Дата", "Название креатива", "Комментарий", 
        "Фикс цена", "Цена заявки", "Цена подписчика", 
        "Заявок подано", "Подписок", 
        "Цена за подписчика", "Цена за заявку"
    ]
    ws.append(headers)
    
    for p in purchases:
        # Fetch details
        creative = await db.get_creative(p.creative_id)
        creative_name = creative.name if creative else f"Unknown #{p.creative_id}"
        
        # Stats (Lifetime for this purchase)
        leads_count = await db.get_leads_count(p.id)
        # Assuming get_subscriptions_count without time args returns total, or pass None/0
        subs_count = await db.get_subscriptions_count(p.id, None, None) 
        
        # Prices
        fix_price = p.price_value if p.pricing_type.value == "FIXED" else 0
        cpl_price = p.price_value if p.pricing_type.value == "CPL" else 0
        cps_price = p.price_value if p.pricing_type.value == "CPS" else 0
        
        # Calculations of actual metrics based on spend
        # Total Spend estimation
        total_spend = 0
        if p.pricing_type.value == "FIXED":
            total_spend = p.price_value
        elif p.pricing_type.value == "CPL":
            total_spend = p.price_value * leads_count
        elif p.pricing_type.value == "CPS":
            total_spend = p.price_value * subs_count
            
        # Cost per Subscriber (CPA)
        cost_per_sub = (total_spend / subs_count) if subs_count > 0 else 0
        
        # Cost per Lead
        cost_per_lead = (total_spend / leads_count) if leads_count > 0 else 0
        
        # Format Date
        date_str = datetime.fromtimestamp(p.created_timestamp).strftime("%d.%m.%Y %H:%M")
        
        row = [
            date_str,
            creative_name,
            p.comment or "",
            fix_price,
            cpl_price,
            cps_price,
            leads_count,
            subs_count,
            round(cost_per_sub, 2),
            round(cost_per_lead, 2)
        ]
        ws.append(row)
        
    # Auto-width
    for column in ws.columns:
        max_length = 0
        column = [cell for cell in column]
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column[0].column_letter].width = adjusted_width

    # Save to memory
    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    
    # Send file
    from aiogram.types import BufferedInputFile
    input_file = BufferedInputFile(file_stream.getvalue(), filename=f"stats_{period_name}.xlsx")
    
    await call.message.answer_document(
        document=input_file,
        caption=f"📊 Статистика закупов за период: {period}"
    )
    # Don't delete or edit previous message, just send doc? 
    # User might want to stay in menu.
    # But usually improved flow is to stay or updated text.
    # The previous message is "Выберите период...". Sending doc as new message is correct.


@router.callback_query(F.data.startswith("AdPurchase|gen_post|"))
async def generate_post(call: CallbackQuery):
    purchase_id = int(call.data.split("|")[2])
    
    # 1. Ensure invite links
    mappings, errors = await db.ensure_invite_links(purchase_id, call.bot)
    
    # Show errors if any
    if errors:
        error_text = "⚠️ Не удалось создать invite-ссылки для некоторых каналов:\n" + "\n".join(errors)
        await call.message.answer(error_text)
    
    # 2. Get Creative
    purchase = await db.get_purchase(purchase_id)
    creative = await db.get_creative(purchase.creative_id)
    
    if not creative or not creative.raw_message:
        await call.answer("Ошибка: креатив не найден или пуст", show_alert=True)
        return

    # 3. Prepare message
    import copy
    import re
    from main_bot.database.types import AdTargetType
    
    message_data = copy.deepcopy(creative.raw_message)
    
    # Generate ref-links for bots
    for m in mappings:
        # Check if this is a bot link that should be tracked
        if m.track_enabled and not m.ref_param:
            # Try to detect bot username from original_url
            # Format: t.me/<username> or https://t.me/<username>
            bot_username_match = re.match(r'(?:https?://)?t\.me/([a-zA-Z0-9_]+)(?:\?|$)', m.original_url)
            
            if bot_username_match and '/' not in bot_username_match.group(1):
                # This looks like a bot link (not a channel with /+)
                bot_username = bot_username_match.group(1)
                ref_param = f"ref_{purchase_id}_{m.slot_id}"
                
                # Update mapping in DB with ref_param
                await db.upsert_link_mapping(
                    ad_purchase_id=purchase_id,
                    slot_id=m.slot_id,
                    ref_param=ref_param
                )
                
                # Update local object
                m.ref_param = ref_param
                
                # Set target_type to BOT if not already set
                if m.target_type != AdTargetType.BOT:
                    await db.upsert_link_mapping(
                        ad_purchase_id=purchase_id,
                        slot_id=m.slot_id,
                        target_type=AdTargetType.BOT
                    )
                    m.target_type = AdTargetType.BOT
    
    # Create a map of original_url -> replacement_link
    url_map = {}
    replaced_count = 0
    for m in mappings:
        # Normalize original URL for matching (strip trailing slash)
        original_key = m.original_url.rstrip("/")
        
        # Priority 1: invite_link (for channels)
        if m.invite_link:
            url_map[original_key] = m.invite_link
            replaced_count += 1
        # Priority 2: ref-link (for bots)
        elif m.ref_param and m.target_type == AdTargetType.BOT:
            # Extract bot username from original URL
            bot_username_match = re.match(r'(?:https?://)?t\.me/([a-zA-Z0-9_]+)', m.original_url)
            if bot_username_match:
                bot_username = bot_username_match.group(1)
                ref_link = f"https://t.me/{bot_username}?start={m.ref_param}"
                url_map[original_key] = ref_link
                # Also map the un-normalized version just in case
                url_map[m.original_url] = ref_link
                replaced_count += 1
            
    # Helper to replace in text
    def replace_links_in_entities(text_content, entities):
        if not entities:
            return
        for entity in entities:
            # Handle text_link (formatted links)
            if entity.get('type') == 'text_link':
                url = entity.get('url')
                if url:
                    # Try exact match first, then normalized
                    normalized_url = url.rstrip("/")
                    if url in url_map:
                        entity['url'] = url_map[url]
                    elif normalized_url in url_map:
                        entity['url'] = url_map[normalized_url]
            
            # Handle url (raw links)
            # Convert them to text_link so the text remains same but points to new URL
            elif entity.get('type') == 'url':
                # Extract URL from text content using offset/length
                offset = entity.get('offset')
                length = entity.get('length')
                url = text_content[offset:offset+length]
                
                if url:
                    normalized_url = url.rstrip("/")
                    target_url = None
                    if url in url_map:
                        target_url = url_map[url]
                    elif normalized_url in url_map:
                        target_url = url_map[normalized_url]
                    
                    if target_url:
                        entity['type'] = 'text_link'
                        entity['url'] = target_url

    # Replace in caption/text entities
    if 'entities' in message_data:
        replace_links_in_entities(message_data.get('text', ''), message_data['entities'])
        
    if 'caption_entities' in message_data:
        replace_links_in_entities(message_data.get('caption', ''), message_data['caption_entities'])
        
    # Replace in inline keyboard
    if 'reply_markup' in message_data and 'inline_keyboard' in message_data['reply_markup']:
        for row in message_data['reply_markup']['inline_keyboard']:
            for btn in row:
                if 'url' in btn:
                    if btn['url'] in url_map:
                        btn['url'] = url_map[btn['url']]

    # 4. Send to user
    try:
        chat_id = call.from_user.id
        reply_markup = message_data.get('reply_markup')
        
        # Helper to safely create entities
        def safe_entities(ent_list):
            if not ent_list: 
                return None
            try:
                # Filter out nulls if any
                return [types.MessageEntity(**e) for e in ent_list if e]
            except Exception:
                return None
        
        final_entities = safe_entities(message_data.get('entities'))
        final_caption_entities = safe_entities(message_data.get('caption_entities'))
        
        # Prioritize media types over text (media messages can have 'text' field but it's actually caption)
        if 'photo' in message_data:
            photo_id = message_data['photo'][-1]['file_id']
            caption = message_data.get('caption', '')
            # Telegram caption limit is 1024 characters
            if len(caption) > 1024:
                await call.answer("Ошибка: Подпись к медиа слишком длинная (макс. 1024 символа).", show_alert=True)
                return
            await call.bot.send_photo(
                chat_id=chat_id,
                photo=photo_id,
                caption=caption if caption else None,
                caption_entities=final_caption_entities,
                reply_markup=reply_markup,
                parse_mode=None
            )
        elif 'video' in message_data:
            video_id = message_data['video']['file_id']
            caption = message_data.get('caption', '')
            if len(caption) > 1024:
                await call.answer("Ошибка: Подпись к медиа слишком длинная (макс. 1024 символа).", show_alert=True)
                return
            await call.bot.send_video(
                chat_id=chat_id,
                video=video_id,
                caption=caption if caption else None,
                caption_entities=final_caption_entities,
                reply_markup=reply_markup,
                parse_mode=None
            )
        elif 'animation' in message_data:
            animation_id = message_data['animation']['file_id']
            caption = message_data.get('caption', '')
            if len(caption) > 1024:
                await call.answer("Ошибка: Подпись к медиа слишком длинная (макс. 1024 символа).", show_alert=True)
                return
            await call.bot.send_animation(
                chat_id=chat_id,
                animation=animation_id,
                caption=caption if caption else None,
                caption_entities=final_caption_entities,
                reply_markup=reply_markup,
                parse_mode=None
            )
        elif 'text' in message_data:
            text = message_data['text']
            # Telegram text message limit is 4096 characters
            if len(text) > 4096:
                await call.answer("Ошибка: Текст сообщения слишком длинный (макс. 4096 символов).", show_alert=True)
                return
            await call.bot.send_message(
                chat_id=chat_id,
                text=text,
                entities=final_entities,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode=None
            )
        else:
            await call.answer("Неподдерживаемый тип сообщения для генерации", show_alert=True)
            return



        success_msg = "☝️☝️☝️ ваш пост для закупа ☝️☝️☝️\n\n✅ Готово! Перешлите это админу для размещения."
        if replaced_count > 0:
            success_msg += f"\n📎 Заменено ссылок: {replaced_count}"
        await call.message.answer(success_msg)
        
        # Redirect to Purchase List
        from main_bot.handlers.user.ad_creative.purchase_menu import show_purchase_list
        await show_purchase_list(call, send_new=True)
        
    except Exception as e:
        # Catch specific errors
        err_str = str(e)
        if "MESSAGE_TOO_LONG" in err_str:
            await call.answer("Ошибка: Сообщение слишком длинное для отправки.", show_alert=True)
        else:
            await call.answer(f"Ошибка при отправке: {e}", show_alert=True)

