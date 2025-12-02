import re
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from main_bot.database.db import db
from main_bot.database.types import AdPricingType, AdTargetType
from main_bot.database.ad_purchase.model import AdPurchase
from main_bot.keyboards.keyboards import keyboards, InlineAdPurchase, InlineAdCreative
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
    
    text = (
        f"🛒 <b>Закуп #{purchase.id}</b>\n"
        f"Креатив: {creative_name}\n"
        f"Тип: {purchase.pricing_type}\n"
        f"Ставка: {purchase.price_value} руб.\n"
        f"Комментарий: {purchase.comment or 'Нет'}\n"
        f"Статус: {purchase.status}"
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


@router.callback_query(F.data.startswith("AdPurchase|archive|"))
async def archive_purchase(call: CallbackQuery):
    purchase_id = int(call.data.split("|")[2])
    await db.update_purchase_status(purchase_id, "archived")
    await call.answer("Закуп архивирован")
    await view_purchase(call, purchase_id)


@router.callback_query(F.data.startswith("AdPurchase|delete|"))
async def delete_purchase(call: CallbackQuery):
    purchase_id = int(call.data.split("|")[2])
    await db.update_purchase_status(purchase_id, "deleted")
    await call.answer("Закуп удален")
    # Go back to list instead of staying on deleted item
    from main_bot.handlers.user.ad_creative.purchase_menu import show_purchase_list
    await show_purchase_list(call)


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
    
    message_data = copy.deepcopy(creative.raw_message)
    
    # Create a map of original_url -> invite_link
    url_map = {}
    replaced_count = 0
    for m in mappings:
        if m.invite_link:
            url_map[m.original_url] = m.invite_link
            replaced_count += 1
            
    # Helper to replace in text
    def replace_links_in_entities(text_content, entities):
        if not entities:
            return
        for entity in entities:
            if entity.get('type') == 'text_link':
                url = entity.get('url')
                if url in url_map:
                    entity['url'] = url_map[url]
                    
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
                caption_entities=[types.MessageEntity(**e) for e in message_data.get('caption_entities', [])] if message_data.get('caption_entities') else None,
                reply_markup=reply_markup
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
                caption_entities=[types.MessageEntity(**e) for e in message_data.get('caption_entities', [])] if message_data.get('caption_entities') else None,
                reply_markup=reply_markup
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
                caption_entities=[types.MessageEntity(**e) for e in message_data.get('caption_entities', [])] if message_data.get('caption_entities') else None,
                reply_markup=reply_markup
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
                entities=[types.MessageEntity(**e) for e in message_data.get('entities', [])] if message_data.get('entities') else None,
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
        else:
            await call.answer("Неподдерживаемый тип сообщения для генерации", show_alert=True)
            return


        success_msg = "✅ Готово! Перешлите это админу для размещения."
        if replaced_count > 0:
            success_msg += f"\n📎 Заменено ссылок: {replaced_count}"
        await call.message.answer(success_msg)
        
    except Exception as e:
        # Catch specific errors
        err_str = str(e)
        if "MESSAGE_TOO_LONG" in err_str:
            await call.answer("Ошибка: Сообщение слишком длинное для отправки.", show_alert=True)
        else:
            await call.answer(f"Ошибка при отправке: {e}", show_alert=True)

